import asyncio
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Merchant
from app.search import visual
from tests.conftest import jpeg, signup


async def test_health_and_headers(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


async def test_signup_login_logout_all(client):
    await signup(client, "a@example.com")
    me = await client.get("/v1/auth/me")
    assert me.json()["email"] == "a@example.com"
    cookie = client.cookies.get("saasta_session")
    await client.post("/v1/auth/logout-all")
    client.cookies.set("saasta_session", cookie)
    assert (await client.get("/v1/auth/me")).status_code == 401  # old token revoked


async def test_weak_password_rejected(client):
    r = await client.post("/v1/auth/signup", json={"email": "w@example.com", "password": "password123"})
    assert r.status_code == 422
    assert "password123" not in r.text


async def test_login_lockout(client):
    await signup(client, "lock@example.com")
    client.cookies.clear()
    for _ in range(8):
        r = await client.post("/v1/auth/login", json={"email": "lock@example.com", "password": "wrong-password"})
        assert r.status_code == 401
    r = await client.post("/v1/auth/login", json={"email": "lock@example.com", "password": "Str0ng-Passw0rd!"})
    assert r.status_code == 401  # locked even with the right password


async def test_cookie_csrf_blocked_from_other_origin(client):
    await signup(client, "csrf@example.com")
    r = await client.post("/v1/auth/logout-all", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


async def test_search_rejects_non_image(client):
    client.cookies.clear()
    r = await client.post("/v1/searches", files={"file": ("x.jpg", b"<svg onload=alert(1)>", "image/jpeg")})
    assert r.status_code == 422


async def test_image_search_end_to_end_with_partner_catalog(client):
    # A verified partner store with one red product.
    await signup(client, "store@example.com")
    r = await client.post("/v1/merchant", json={"name": "Red Store", "domain": "redstore.pk"})
    assert r.status_code == 201
    async with SessionLocal() as db:
        await db.execute(update(Merchant).where(Merchant.domain == "redstore.pk").values(domain_verified=True))
        await db.commit()
    r = await client.post("/v1/merchant/catalog", json={"items": [
        {"external_id": "1", "title": "Red kurta lawn", "url": "https://redstore.pk/p/1",
         "image_url": "https://redstore.pk/i/1.jpg", "price": 3500},
        {"external_id": "2", "title": "Stolen", "url": "https://other.pk/p/2",
         "image_url": "https://other.pk/i/2.jpg", "price": 10},
    ]})
    body = r.json()
    assert body["accepted"] == 1 and body["rejected_count"] == 1  # foreign domain refused
    # Fingerprint directly (no network in tests).
    from sqlalchemy import select

    from app.models import CatalogItem
    fp = visual.fingerprint_bytes(jpeg())
    async with SessionLocal() as db:
        item = (await db.execute(select(CatalogItem))).scalar_one()
        item.phash, item.embedding = fp["phash"], visual.hist_to_bytes(fp["hist"])
        await db.commit()

    client.cookies.clear()
    r = await client.post("/v1/searches", files={"file": ("a.jpg", jpeg(), "image/jpeg")})
    assert r.status_code == 202
    sid = r.json()["id"]
    for _ in range(50):
        res = (await client.get(f"/v1/searches/{sid}")).json()
        if res["status"] in ("done", "failed"):
            break
        await asyncio.sleep(0.1)
    assert res["status"] == "done", res
    result = res["result"]
    assert result["understanding"]["color"] == "red"
    top = (result["exact"] + result["similar"])[0]
    assert top["partner"] is True and top["domain"] == "redstore.pk"

    # Signed click-out works; tampered target does not (no open redirect).
    out = top["out"]
    r = await client.get(out, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://redstore.pk/p/1"
    qs = parse_qs(urlsplit(out).query)
    bad = f"/v1/out?s={qs['s'][0]}&u=https%3A%2F%2Fevil.example&sig={qs['sig'][0]}"
    assert (await client.get(bad, follow_redirects=False)).status_code == 400

    # Image is served as clean JPEG.
    img = await client.get(f"/v1/media/{res['image']}")
    assert img.headers["content-type"] == "image/jpeg"
    assert (await client.get("/v1/media/..%2F..%2Fetc%2Fpasswd")).status_code == 404


async def test_widget_requires_key_and_origin(client):
    await signup(client, "w@shop.com")
    await client.post("/v1/merchant", json={"name": "W Shop", "domain": "wshop.pk"})
    key = (await client.post("/v1/merchant/keys", json={"label": "site"})).json()["key"]
    client.cookies.clear()
    files = {"file": ("a.jpg", jpeg(), "image/jpeg")}
    assert (await client.post("/w/v1/widget/search", files=files)).status_code == 401
    r = await client.post("/w/v1/widget/search", files=files,
                          headers={"X-API-Key": key, "Origin": "https://evil.example"})
    assert r.status_code == 403
    r = await client.post("/w/v1/widget/search", files=files,
                          headers={"X-API-Key": key, "Origin": "https://www.wshop.pk"})
    assert r.status_code == 200
    pre = await client.options("/w/v1/widget/search", headers={
        "Origin": "https://www.wshop.pk", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-api-key"})
    assert pre.status_code == 200


async def test_boards_sanitize_links(client):
    await signup(client, "b@example.com")
    r = await client.post("/v1/me/boards", json={"title": "Eid", "public": True, "items": [
        {"title": "ok", "url": "https://daraz.pk/x", "price_local": 100},
        {"title": "xss", "url": "javascript:alert(1)"}]})
    bid = r.json()["id"]
    client.cookies.clear()
    board = (await client.get(f"/v1/boards/{bid}")).json()
    assert [i["title"] for i in board["items"]] == ["ok"] and board["total"] == 100


async def test_account_deletion(client):
    await signup(client, "del@example.com")
    assert (await client.delete("/v1/auth/me")).status_code == 204
    r = await client.post("/v1/auth/login", json={"email": "del@example.com", "password": "Str0ng-Passw0rd!"})
    assert r.status_code == 401
