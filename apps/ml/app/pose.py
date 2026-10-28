"""Whole-body pose estimation with DWPose ONNX weights (YOLOX person detector + RTMPose head).

Our own minimal inference code: no framework beyond onnxruntime + numpy.
Returns the 17 COCO body keypoints (x, y, score) of the most prominent person.
"""
import os
import threading

import numpy as np
from PIL import Image

from app.config import settings

_lock = threading.Lock()
_det = _pose = None
MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float32)
STD = np.array([58.395, 57.12, 57.375], dtype=np.float32)


def _sessions():
    global _det, _pose
    if _det is None:
        with _lock:
            if _det is None:
                import onnxruntime as ort

                d = os.path.join(settings().tryon_weights, "dwpose")
                opts = ort.SessionOptions()
                prov = ["CPUExecutionProvider"]
                _det = ort.InferenceSession(os.path.join(d, "yolox_l.onnx"), opts, providers=prov)
                _pose = ort.InferenceSession(os.path.join(d, "dw-ll_ucoco_384.onnx"), opts, providers=prov)
    return _det, _pose


def available() -> bool:
    d = os.path.join(settings().tryon_weights, "dwpose")
    return all(os.path.exists(os.path.join(d, f)) for f in ("yolox_l.onnx", "dw-ll_ucoco_384.onnx"))


def _detect_person(det, rgb: np.ndarray) -> np.ndarray | None:
    h, w = rgb.shape[:2]
    r = min(640 / h, 640 / w)
    resized = np.asarray(Image.fromarray(rgb).resize((int(w * r), int(h * r)), Image.BILINEAR), dtype=np.float32)
    canvas = np.full((640, 640, 3), 114, dtype=np.float32)
    canvas[: resized.shape[0], : resized.shape[1]] = resized[:, :, ::-1]  # YOLOX expects BGR
    out = det.run(None, {det.get_inputs()[0].name: canvas.transpose(2, 0, 1)[None]})[0][0]
    # decode grid outputs
    grids, strides = [], []
    for s in (8, 16, 32):
        n = 640 // s
        yv, xv = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
        strides.append(np.full((n * n, 1), s))
    grids, strides = np.concatenate(grids), np.concatenate(strides)
    out[:, :2] = (out[:, :2] + grids) * strides
    out[:, 2:4] = np.exp(out[:, 2:4]) * strides
    scores = out[:, 4] * out[:, 5]  # objectness * person class
    i = int(scores.argmax())
    if scores[i] < 0.3:
        return None
    cx, cy, bw, bh = out[i, :4] / r
    return np.array([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2])


def keypoints(img: Image.Image) -> np.ndarray | None:
    det, pose = _sessions()
    rgb = np.asarray(img.convert("RGB"))
    box = _detect_person(det, rgb)
    if box is None:
        return None
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw, bh = (x1 - x0) * 1.25, (y1 - y0) * 1.25
    # keep the 288x384 (w:h = 3:4) aspect ratio
    if bw / bh > 0.75:
        bh = bw / 0.75
    else:
        bw = bh * 0.75
    crop_box = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    crop = img.convert("RGB").crop(tuple(int(round(v)) for v in crop_box)).resize((288, 384), Image.BILINEAR)
    x = (np.asarray(crop, dtype=np.float32) - MEAN) / STD
    sx, sy = pose.run(None, {pose.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})
    sx, sy = sx[0], sy[0]
    px = sx.argmax(1) / 2.0
    py = sy.argmax(1) / 2.0
    conf = np.minimum(sx.max(1), sy.max(1))
    kp = np.stack([crop_box[0] + px / 288 * bw, crop_box[1] + py / 384 * bh, conf], 1)
    return kp[:17]
