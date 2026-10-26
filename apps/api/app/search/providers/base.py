from typing import Protocol

from app.search.types import Offer, Query


class Provider(Protocol):
    name: str

    def enabled(self) -> bool: ...

    async def search(self, q: Query) -> tuple[list[Offer], dict]:
        """Return offers plus provider hints (e.g. a guessed product title)."""
        ...


def parse_price(raw) -> tuple[float | None, str | None]:
    """Accepts SerpApi-style {'value':..,'currency':..} or strings like 'Rs 4,999' / '$12.50'."""
    if raw is None:
        return None, None
    if isinstance(raw, dict):
        v = raw.get("extracted_value") or raw.get("value")
        cur = raw.get("currency")
        try:
            return (float(v) if v is not None else None), _cur(cur)
        except (TypeError, ValueError):
            return parse_price(str(v))[0], _cur(cur)
    if isinstance(raw, (int, float)):
        return float(raw), None
    text = str(raw)
    cur = _cur(text)
    digits = "".join(ch for ch in text if ch.isdigit() or ch in ".,")
    if not digits:
        return None, cur
    # 1,299.00 / 1.299,00 / 4,999
    if "," in digits and "." in digits:
        if digits.rfind(",") > digits.rfind("."):
            digits = digits.replace(".", "").replace(",", ".")
        else:
            digits = digits.replace(",", "")
    elif "," in digits:
        tail = digits.split(",")[-1]
        digits = digits.replace(",", "" if len(tail) == 3 else ".")
    try:
        return float(digits.strip(".")), cur
    except ValueError:
        return None, cur


_SYMBOLS = [
    ("PKR", "PKR"), ("Rs", "PKR"), ("₨", "PKR"), ("INR", "INR"), ("₹", "INR"), ("AED", "AED"),
    ("SAR", "SAR"), ("GBP", "GBP"), ("£", "GBP"), ("EUR", "EUR"), ("€", "EUR"), ("USD", "USD"),
    ("US$", "USD"), ("$", "USD"),
]


def _cur(text) -> str | None:
    if not text:
        return None
    t = str(text)
    if len(t) == 3 and t.isalpha():
        return t.upper()
    for sym, code in _SYMBOLS:
        if sym in t:
            return code
    return None
