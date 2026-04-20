"""CSRF Double Submit Cookie 미들웨어."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from alphapulse.webapp.middleware.csrf import CSRFMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware, secret="x" * 32)

    @app.get("/api/v1/csrf-token")
    async def token(request: Request):
        return {"token": request.state.csrf_token}

    @app.post("/api/v1/x")
    async def post():
        return {"ok": True}

    @app.get("/api/v1/y")
    async def get():
        return {"ok": True}

    return app


class TestCSRFMiddleware:
    def test_get_allowed_without_token(self):
        client = TestClient(_app())
        r = client.get("/api/v1/y")
        assert r.status_code == 200

    def test_post_without_token_rejected(self):
        client = TestClient(_app())
        r = client.post("/api/v1/x")
        assert r.status_code == 403

    def test_post_with_matching_token_accepted(self):
        client = TestClient(_app())
        r1 = client.get("/api/v1/csrf-token")
        token = r1.json()["token"]
        r2 = client.post(
            "/api/v1/x", headers={"X-CSRF-Token": token},
            cookies={"ap_csrf": token},
        )
        assert r2.status_code == 200

    def test_post_with_mismatched_token_rejected(self):
        client = TestClient(_app())
        client.get("/api/v1/csrf-token")
        r = client.post(
            "/api/v1/x", headers={"X-CSRF-Token": "wrong"},
            cookies={"ap_csrf": "other"},
        )
        assert r.status_code == 403
