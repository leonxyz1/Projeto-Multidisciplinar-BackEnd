from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from src.infrastructure.database.connection import SessionLocal
from src.infrastructure.database.models import UsuarioModel
from src.infrastructure.security import JWT_ALGORITHM, get_jwt_secret


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> UsuarioModel:
    try:
        claims = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id = int(claims["sub"])
        token_profile = claims["perfil"]
    except (JWTError, KeyError, TypeError, ValueError):
        raise _unauthorized() from None

    user = session.get(UsuarioModel, user_id)
    if user is None or token_profile != user.perfil:
        raise _unauthorized()
    return user


def require_profile(*allowed_profiles: str) -> Callable[..., UsuarioModel]:
    def check_profile(
        current_user: Annotated[UsuarioModel, Depends(get_current_user)],
    ) -> UsuarioModel:
        if current_user.perfil not in allowed_profiles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Perfil sem permissão para este recurso",
            )
        return current_user

    return check_profile
