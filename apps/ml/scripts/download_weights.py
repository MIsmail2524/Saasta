"""Download open model weights once onto our own servers. After this, nothing calls out at runtime.

  python scripts/download_weights.py --dir ./weights/tryon

Weights (all permit commercial use, check LICENSES.md before upgrading any of them):
  - FASHN VTON v1.5 try-on model          Apache-2.0   fashn-ai/fashn-vton-1.5
  - DWPose (YOLOX-L + RTMPose-L wholebody) Apache-2.0   yzd-v/DWPose
  - Marqo-FashionSigLIP is pulled by open_clip into the HF cache on first start (Apache-2.0)
"""
import argparse
import os

from huggingface_hub import hf_hub_download

FILES = [
    ("fashn-ai/fashn-vton-1.5", "model.safetensors", ""),
    ("yzd-v/DWPose", "yolox_l.onnx", "dwpose"),
    ("yzd-v/DWPose", "dw-ll_ucoco_384.onnx", "dwpose"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="./weights/tryon")
    ap.add_argument("--skip-tryon", action="store_true", help="only pose weights (for accessory try-on)")
    args = ap.parse_args()
    for repo, name, sub in FILES:
        if args.skip_tryon and name == "model.safetensors":
            continue
        dest = os.path.join(args.dir, sub)
        os.makedirs(dest, exist_ok=True)
        path = hf_hub_download(repo, name, local_dir=dest)
        print(f"{repo}/{name} -> {path}")


if __name__ == "__main__":
    main()
