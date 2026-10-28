"""Fashion image/text embeddings in one shared space (SigLIP architecture, fashion-tuned weights)."""
import io
import threading

import numpy as np
import torch
from PIL import Image

from app.config import settings

_lock = threading.Lock()
_model = _preprocess = _tokenizer = None


def _load():
    global _model, _preprocess, _tokenizer
    if _model is None:
        with _lock:
            if _model is None:
                import open_clip

                s = settings()
                model, _, preprocess = open_clip.create_model_and_transforms(s.embed_model)
                if s.embed_checkpoint:
                    state = torch.load(s.embed_checkpoint, map_location="cpu", weights_only=True)
                    model.load_state_dict(state.get("model", state))
                model.eval()
                _model, _preprocess = model, preprocess
                _tokenizer = open_clip.get_tokenizer(s.embed_model)
    return _model, _preprocess, _tokenizer


def loaded() -> bool:
    return _model is not None


@torch.inference_mode()
def images(jpegs: list[bytes]) -> np.ndarray:
    model, preprocess, _ = _load()
    batch = torch.stack([preprocess(Image.open(io.BytesIO(j)).convert("RGB")) for j in jpegs])
    v = model.encode_image(batch)
    v = v / v.norm(dim=-1, keepdim=True)
    return v.float().numpy()


@torch.inference_mode()
def texts(items: list[str]) -> np.ndarray:
    model, _, tokenizer = _load()
    v = model.encode_text(tokenizer(items))
    v = v / v.norm(dim=-1, keepdim=True)
    return v.float().numpy()
