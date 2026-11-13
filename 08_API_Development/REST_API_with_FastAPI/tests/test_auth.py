"""
REST API with FastAPI - Unit Tests for Auth
"""

import pytest
from datetime import datetime, timedelta, timezone
from src.auth import (
    create_access_token, verify_password, get_password_hash,
    authenticate_user, SECRET_KEY, ALGORITHM
)
from src.database import User
from src.schemas import TokenData
from jose import jwt


class TestAuth:
    def test_get_password_hash(self):
        password = "SecurePass123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert len(hashed) > 20

    def test_verify_password_correct(self):
        password = "SecurePass123"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "SecurePass123"
        hashed = get_password_hash(password)
        assert verify_password("WrongPass123", hashed) is False

    def test_create_access_token(self):
        data = {"sub": "testuser"}
        token = create_access_token(data)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_access_token_with_expiry(self):
        data = {"sub": "testuser"}
        expires = timedelta(minutes=30)
        token = create_access_token(data, expires_delta=expires)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_default_expiry(self):
        data = {"sub": "testuser"}
        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        # Default should be ACCESS_TOKEN_EXPIRE_MINUTES (30 minutes)
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = exp_time - now
        assert 29 <= diff.total_seconds() / 60 <= 31