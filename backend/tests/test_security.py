"""Unit tests for password hashing and JWT — no DB required."""
from __future__ import annotations

import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-pw")
    assert hashed != "s3cret-pw"
    assert verify_password("s3cret-pw", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_carries_role_and_type():
    token = create_access_token("user-123", "researcher")
    claims = decode_token(token)
    assert claims["sub"] == "user-123"
    assert claims["type"] == "access"
    assert claims["role"] == "researcher"


def test_refresh_token_type():
    claims = decode_token(create_refresh_token("user-123"))
    assert claims["type"] == "refresh"


def test_tampered_token_rejected():
    from app.core.security import JWTError

    with pytest.raises(JWTError):
        decode_token("not.a.valid.token")
