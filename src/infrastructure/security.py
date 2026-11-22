import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt


JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if secret is None or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 bytes")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if len(password.encode("utf-8")) > 72:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int, profile: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    claims = {"sub": str(user_id), "perfil": profile, "exp": expires_at}
    return jwt.encode(claims, get_jwt_secret(), algorithm=JWT_ALGORITHM)
