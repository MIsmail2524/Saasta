import re

from pydantic import BaseModel, EmailStr, Field, model_validator


class _Strict(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class SignupIn(_Strict):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    name: str | None = Field(default=None, max_length=120)


class LoginIn(_Strict):
    email: EmailStr
    password: str = Field(max_length=128)


class PasswordChangeIn(_Strict):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    role: str


class SearchUrlIn(_Strict):
    url: str | None = Field(default=None, max_length=2048)
    text: str | None = Field(default=None, max_length=300)
    country: str = Field(default="pk", pattern=r"^[a-z]{2}$")
    currency: str = Field(default="PKR", pattern=r"^[A-Z]{3}$")


_DOMAIN = re.compile(r"^(?=.{4,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,24}$")


_HANDLE = re.compile(r"^[a-z0-9._]{2,30}$")


class MerchantIn(_Strict):
    name: str = Field(min_length=2, max_length=120)
    kind: str = Field(default="store", pattern=r"^(store|social)$")
    # store: their website domain. social: their Instagram/TikTok handle.
    domain: str = Field(max_length=253)
    platform: str = Field(default="instagram", pattern=r"^(instagram|tiktok)$")
    country: str = Field(default="pk", pattern=r"^[a-z]{2}$")
    currency: str = Field(default="PKR", pattern=r"^[A-Z]{3}$")
    allow_training: bool = False

    @model_validator(mode="after")
    def clean_domain(self):
        v = self.domain.lower().strip()
        if self.kind == "social":
            handle = v.rstrip("/").split("/")[-1].removeprefix("@")
            if not _HANDLE.match(handle):
                raise ValueError("enter your handle like @mystore")
            self.domain = f"{self.platform}.com/{handle}"
            return self
        v = v.removeprefix("https://").removeprefix("http://").split("/")[0].removeprefix("www.")
        if not _DOMAIN.match(v):
            raise ValueError("enter a domain like mystore.pk")
        self.domain = v
        return self


class CatalogItemIn(_Strict):
    external_id: str = Field(max_length=128)
    title: str = Field(max_length=300)
    url: str = Field(max_length=2048)
    image_url: str = Field(max_length=2048)
    price: float | None = Field(default=None, ge=0, le=1e9)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    category: str | None = Field(default=None, max_length=40)
    in_stock: bool = True


class CatalogUploadIn(_Strict):
    items: list[CatalogItemIn] = Field(max_length=2000)


class ShopifyImportIn(_Strict):
    max_products: int = Field(default=500, ge=1, le=5000)


class ApiKeyIn(_Strict):
    label: str = Field(default="default", max_length=60)


class WatchIn(_Strict):
    title: str = Field(max_length=300)
    url: str = Field(max_length=2048)
    image_url: str | None = Field(default=None, max_length=2048)
    price: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="PKR", pattern=r"^[A-Z]{3}$")


class BoardIn(_Strict):
    title: str = Field(min_length=1, max_length=120)
    public: bool = False
    note: str | None = Field(default=None, max_length=2000)
    items: list[dict] = Field(default_factory=list, max_length=60)


