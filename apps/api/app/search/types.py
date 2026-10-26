from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit


@dataclass
class Offer:
    title: str
    url: str
    source: str  # google_lens | google_shopping | instagram | tiktok | partner
    image: str | None = None
    price: float | None = None
    currency: str | None = None
    price_text: str | None = None
    rating: float | None = None
    reviews: int | None = None
    seller: str | None = None
    in_stock: bool | None = None
    match: str = "similar"  # exact | similar
    partner: bool = False
    merchant_id: str | None = None
    similarity: float | None = None
    price_local: float | None = None
    trust: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    @property
    def domain(self) -> str:
        host = (urlsplit(self.url).hostname or "").lower()
        return host[4:] if host.startswith("www.") else host

    def to_dict(self) -> dict:
        d = asdict(self)
        d["domain"] = self.domain
        return d


@dataclass
class Query:
    image_url: str | None = None  # publicly reachable copy of the cleaned image
    image_bytes: bytes | None = None
    text: str | None = None
    country: str = "pk"
    currency: str = "PKR"
    max_price: float | None = None
    color: str | None = None
