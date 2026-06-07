from datetime import timedelta

import pytest

from backend.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_correct_password() -> None:
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_wrong_password_returns_false() -> None:
    hashed = hash_password("mysecret")
    assert verify_password("wrong", hashed) is False


def test_hash_is_not_plaintext() -> None:
    assert hash_password("mysecret") != "mysecret"


def test_two_hashes_of_same_password_differ() -> None:
    # bcrypt uses a random salt each time
    assert hash_password("mysecret") != hash_password("mysecret")


def test_create_and_decode_token_roundtrip() -> None:
    token = create_access_token({"sub": "user-123"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"


def test_decode_token_contains_expiry() -> None:
    token = create_access_token({"sub": "user-123"})
    payload = decode_access_token(token)
    assert payload is not None
    assert "exp" in payload


def test_expired_token_returns_none() -> None:
    token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


def test_tampered_token_returns_none() -> None:
    token = create_access_token({"sub": "user-123"})
    tampered = token[:-4] + "XXXX"
    assert decode_access_token(tampered) is None


def test_garbage_token_returns_none() -> None:
    assert decode_access_token("not.a.token") is None
