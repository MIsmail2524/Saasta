"""Virtual try-on via FASHN. Apparel uses tryon-v1.6; shoes/bags/jewellery/eyewear use tryon-max."""
import base64

import httpx

from app.core.config import get_settings

API = "https://api.fashn.ai/v1"
APPAREL = {"tops", "bottoms", "one-pieces", "auto"}


def _data_uri(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


async def start(person_jpeg: bytes, garment_jpeg: bytes, category: str, accessory: bool) -> str:
    key = get_settings().fashn_api_key
    if accessory:
        body = {"model_name": "tryon-max", "inputs": {
            "model_image": _data_uri(person_jpeg), "product_image": _data_uri(garment_jpeg),
            "output_format": "jpeg", "resolution": "1k"}}
    else:
        body = {"model_name": "tryon-v1.6", "inputs": {
            "model_image": _data_uri(person_jpeg), "garment_image": _data_uri(garment_jpeg),
            "category": category if category in APPAREL else "auto",
            "moderation_level": "conservative", "output_format": "jpeg", "mode": "balanced"}}
    async with httpx.AsyncClient(timeout=30, trust_env=False) as c:
        r = await c.post(f"{API}/run", json=body, headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        data = r.json()
    if data.get("error") or not data.get("id"):
        raise RuntimeError("try-on provider rejected the request")
    return data["id"]


async def status(job_id: str) -> tuple[str, str | None, str | None]:
    key = get_settings().fashn_api_key
    async with httpx.AsyncClient(timeout=15, trust_env=False) as c:
        r = await c.get(f"{API}/status/{job_id}", headers={"Authorization": f"Bearer {key}"})
        r.raise_for_status()
        d = r.json()
    st = d.get("status")
    if st == "completed":
        return "done", (d.get("output") or [None])[0], None
    if st == "failed":
        return "failed", None, ((d.get("error") or {}).get("message") or "Try-on failed")[:300]
    return "running", None, None
