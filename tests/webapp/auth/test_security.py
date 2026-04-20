"""인증 보안 유틸 테스트."""
import pytest

from alphapulse.webapp.auth.security import (
    generate_session_token,
    hash_password,
    verify_password,
)


class TestPasswordHash:
    def test_hash_is_not_plaintext(self):
        h = hash_password("s3cret-longenough!")
        assert "s3cret-longenough!" not in h
        assert h.startswith("$2b$")  # bcrypt

    def test_verify_correct(self):
        h = hash_password("s3cret-longenough!")
        assert verify_password("s3cret-longenough!", h)

    def test_verify_wrong(self):
        h = hash_password("s3cret-longenough!")
        assert not verify_password("wrong!", h)

    def test_rejects_short_password(self):
        with pytest.raises(ValueError, match="12"):
            hash_password("short")


class TestSessionToken:
    def test_token_length(self):
        t = generate_session_token()
        assert len(t) >= 40          # secrets.token_urlsafe(32) ≈ 43

    def test_tokens_unique(self):
        assert generate_session_token() != generate_session_token()
