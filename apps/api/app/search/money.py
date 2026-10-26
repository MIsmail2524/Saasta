"""Approximate currency normalisation so prices from different countries are comparable.

Rates are deliberately static + overridable (SAASTA_FX_JSON); results are labelled "approx".
"""
import json
import os

# Units of currency per 1 USD (refresh periodically via env).
_DEFAULT = {"USD": 1.0, "PKR": 281.0, "INR": 84.0, "AED": 3.67, "SAR": 3.75, "GBP": 0.77,
            "EUR": 0.92, "CAD": 1.38, "AUD": 1.52, "BDT": 120.0, "TRY": 34.0, "CNY": 7.2}


def _rates() -> dict:
    raw = os.environ.get("SAASTA_FX_JSON")
    if raw:
        try:
            return {**_DEFAULT, **{k.upper(): float(v) for k, v in json.loads(raw).items()}}
        except (ValueError, AttributeError):
            pass
    return _DEFAULT


def convert(amount: float | None, src: str | None, dst: str) -> float | None:
    if amount is None:
        return None
    r = _rates()
    src = (src or dst).upper()
    if src not in r or dst.upper() not in r:
        return None
    return round(amount / r[src] * r[dst.upper()], 2)
