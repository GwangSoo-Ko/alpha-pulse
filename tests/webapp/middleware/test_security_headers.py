"""보안 헤더 미들웨어."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphapulse.webapp.middleware.security_headers import (
    SecurityHeadersMiddleware,
)


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/x")
    async def x():
        return {"ok": True}
    return app


class TestSecurityHeaders:
    def test_headers_present(self):
        client = TestClient(_app())
        r = client.get("/x")
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert "strict-origin" in r.headers["Referrer-Policy"]
        assert "default-src" in r.headers["Content-Security-Policy"]
