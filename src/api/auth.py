from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user, get_db
from src.infrastructure.database.models import UsuarioModel
from src.infrastructure.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["Autenticação"])


class RegisterRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)

    @field_validator("senha")
    @classmethod
    def validate_bcrypt_length(cls, password: str) -> str:
        if len(password.encode("utf-8")) > 72:
            raise ValueError("A senha deve ter no máximo 72 bytes")
        return password


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    perfil: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post(
    "/cadastro",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    session: Annotated[Session, Depends(get_db)],
) -> UsuarioModel:
    email = str(payload.email).lower()
    existing_user = session.scalar(
        select(UsuarioModel.id).where(UsuarioModel.email == email)
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-mail já cadastrado",
        )

    nome = payload.nome.strip()
    if not nome:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O nome não pode ficar vazio",
        )

    user = UsuarioModel(
        nome=nome,
        email=email,
        senha_hash=hash_password(payload.senha),
        perfil="CLIENTE",
    )

    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        duplicate = session.scalar(
            select(UsuarioModel.id).where(UsuarioModel.email == email)
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="E-mail já cadastrado",
            ) from None
        raise
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    email = form.username.strip().lower()
    user = session.scalar(select(UsuarioModel).where(UsuarioModel.email == email))
    if user is None or not verify_password(form.password, user.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.perfil),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
def current_user(
    user: Annotated[UsuarioModel, Depends(get_current_user)],
) -> UsuarioModel:
    return user
