"""Zero-shot product understanding with our own fashion model.

Image vectors are compared with text prompts in the same embedding space, so we get category,
colour and attributes without any external service. Prompt vectors are computed once and cached.
"""
import numpy as np

from app import ml_client

CATEGORY_PROMPTS = {
    "eastern": ["a shalwar kameez", "an embroidered kurta", "a lawn suit", "a lehenga", "a saree", "a kurti",
                "a sherwani", "an abaya"],
    "tops": ["a t-shirt", "a shirt", "a hoodie", "a sweater", "a jacket", "a blouse"],
    "bottoms": ["jeans", "trousers", "a skirt", "shorts"],
    "dresses": ["a dress", "a gown", "a jumpsuit"],
    "shoes": ["sneakers", "high heels", "sandals", "khussa shoes", "boots", "loafers", "slippers"],
    "bags": ["a handbag", "a clutch bag", "a backpack", "a tote bag", "a wallet"],
    "jewellery": ["a necklace", "earrings", "jhumka earrings", "a bracelet", "bangles", "a ring"],
    "watches": ["a wrist watch"],
    "eyewear": ["sunglasses", "eyeglasses"],
}
COLORS = ["black", "white", "grey", "red", "maroon", "pink", "orange", "yellow", "mustard", "green", "olive",
          "teal", "blue", "navy", "purple", "beige", "brown", "gold", "silver", "multicolour"]
ATTRIBUTES = ["embroidered", "printed", "plain", "floral", "sequinned", "mirror work", "striped", "checked",
              "denim", "leather", "silk", "chiffon", "cotton", "velvet", "knitted", "oversized", "gold plated"]

_cache: dict[str, tuple[list[str], np.ndarray]] = {}


async def _bank(name: str, labels: list[str], template: str) -> tuple[list[str], np.ndarray]:
    if name not in _cache:
        _cache[name] = (labels, await ml_client.embed_texts([template.format(x) for x in labels]))
    return _cache[name]


async def _categories() -> tuple[list[str], np.ndarray]:
    if "cat" not in _cache:
        keys, prompts = [], []
        for cat, ps in CATEGORY_PROMPTS.items():
            for p in ps:
                keys.append(cat)
                prompts.append(f"a product photo of {p}")
        _cache["cat"] = (keys, await ml_client.embed_texts(prompts))
    return _cache["cat"]


def _softmax(x: np.ndarray, t: float = 100.0) -> np.ndarray:
    e = np.exp((x - x.max()) * t)
    return e / e.sum()


async def understand(vec: np.ndarray) -> dict:
    keys, cat_vecs = await _categories()
    cat_scores = cat_vecs @ vec
    best = int(cat_scores.argmax())
    category, item_prompt = keys[best], _item_name(best)

    colors, col_vecs = await _bank("color", COLORS, "a photo of a {} fashion item")
    cp = _softmax(col_vecs @ vec)
    color = colors[int(cp.argmax())]

    attrs, attr_vecs = await _bank("attr", ATTRIBUTES, "a photo of a {} fashion item")
    ap = _softmax(attr_vecs @ vec)
    top_attrs = [attrs[i] for i in np.argsort(-ap)[:2] if ap[i] > 0.2]

    query = " ".join([color, *top_attrs[:1], item_prompt]).strip()
    return {"category": category, "color": color, "attributes": top_attrs, "query": query,
            "confidence": round(float(_softmax(cat_scores).max()), 3)}


def _item_name(idx: int) -> str:
    flat = [p for ps in CATEGORY_PROMPTS.values() for p in ps]
    name = flat[idx]
    for art in ("a ", "an "):
        name = name.removeprefix(art)
    return name
