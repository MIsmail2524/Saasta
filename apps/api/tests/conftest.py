import io
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="saasta-test-")
os.environ.update({
    "SAASTA_ENV": "test",
    "SAASTA_DATABASE_URL": f"sqlite+aiosqlite:///{_tmp}/test.db",
    "SAASTA_UPLOAD_DIR": f"{_tmp}/uploads",
    "SAASTA_SECRET_KEY": "test-secret-key-test-secret-key-0123456789",
    "SAASTA_RL_AUTH_PER_MIN": "1000",
    "SAASTA_RL_SEARCH_PER_MIN": "1000",
    "SAASTA_ML_URL": "",
})

import httpx  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

WEB = "http://localhost:3000"


@pytest.fixture(scope="session")
async def client():
    await init_db()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test",
                                 headers={"Origin": WEB}) as c:
        yield c


def jpeg(color=(200, 30, 40), size=(300, 400), exif=False) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    if exif:
        ex = Image.Exif()
        ex[0x010F] = "SecretCam"  # Make
        img.save(buf, "JPEG", exif=ex.tobytes())
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


async def signup(client, email, password="Str0ng-Passw0rd!"):
    client.cookies.clear()
    r = await client.post("/v1/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r
