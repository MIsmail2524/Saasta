"""Turn provider hints into a clean product understanding: category, query, colour, refinements."""
import re
from collections import Counter

CATEGORIES = {
    "shoes": ["shoe", "sneaker", "trainer", "heel", "sandal", "boot", "loafer", "khussa", "kolhapuri",
              "slipper", "flat", "pump", "jogger", "chappal", "mule", "oxford"],
    "bags": ["bag", "handbag", "tote", "clutch", "backpack", "purse", "wallet", "crossbody", "satchel"],
    "jewellery": ["ring", "necklace", "earring", "jhumka", "bracelet", "bangle", "pendant", "chain",
                  "anklet", "payal", "tikka", "nath", "choker", "jewel"],
    "watches": ["watch", "smartwatch", "chronograph"],
    "eyewear": ["sunglass", "glasses", "eyewear", "spectacle"],
    "eastern": ["kurta", "kurti", "shalwar", "kameez", "lawn", "saree", "sari", "lehenga", "dupatta",
                "sherwani", "waistcoat", "abaya", "peshwas", "anarkali", "gharara", "sharara", "unstitched"],
    "tops": ["shirt", "t-shirt", "tshirt", "tee", "top", "blouse", "hoodie", "sweater", "polo", "jacket",
             "coat", "blazer", "cardigan", "sweatshirt"],
    "bottoms": ["jeans", "trouser", "pant", "short", "skirt", "legging", "chino", "cargo"],
    "dresses": ["dress", "gown", "jumpsuit", "maxi", "frock"],
}

TRYON_CATEGORY = {"tops": "tops", "bottoms": "bottoms", "dresses": "one-pieces", "eastern": "one-pieces"}

_PRICE_RE = re.compile(r"(?:under|below|less than|<|max|upto|up to)\s*(?:rs\.?|pkr|\$)?\s*([\d,]+)\s*(k)?", re.I)
_NOISE = re.compile(
    r"\b(buy|online|price in pakistan|pakistan|free shipping|sale|new arrival|best|cheap|official|"
    r"store|shop|original|imported|cod|\d+% off)\b|[|•–—-].*$",
    re.I,
)


def categorize(texts: list[str]) -> str | None:
    votes: Counter = Counter()
    for t in texts:
        low = t.lower()
        for cat, words in CATEGORIES.items():
            if any(re.search(rf"\b{re.escape(w)}", low) for w in words):
                votes[cat] += 1
    return votes.most_common(1)[0][0] if votes else None


def best_query(titles: list[str], fallback: str | None = None) -> str | None:
    """Pick the words that recur across the top matching titles: usually brand + model."""
    if not titles:
        return fallback
    cleaned = [_NOISE.sub("", t).strip() for t in titles if t]
    words: Counter = Counter()
    for t in cleaned:
        for w in dict.fromkeys(re.findall(r"[A-Za-z0-9']{2,}", t.lower())):
            words[w] += 1
    common = {w for w, n in words.items() if n >= max(2, len(cleaned) // 3)}
    if not common:
        return cleaned[0][:80] or fallback
    # keep order of first title for readability
    first = re.findall(r"[A-Za-z0-9']{2,}", cleaned[0])
    out = [w for w in first if w.lower() in common][:8]
    return " ".join(out) or cleaned[0][:80]


def parse_refinement(text: str | None) -> dict:
    """'same but black under 5k' -> {color: black, max_price: 5000, rest: 'same but'}"""
    if not text:
        return {}
    out: dict = {}
    m = _PRICE_RE.search(text)
    if m:
        v = float(m.group(1).replace(",", ""))
        out["max_price"] = v * 1000 if m.group(2) else v
        text = _PRICE_RE.sub("", text)
    from app.search.visual import COLORS

    for c in COLORS:
        if re.search(rf"\b{c}\b", text, re.I):
            out["color"] = c
            break
    out["rest"] = re.sub(r"\s+", " ", text).strip()
    return out
