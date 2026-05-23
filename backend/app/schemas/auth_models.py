from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import datetime


def _check_password_strength(v: str) -> str:
    errors = []
    if len(v) < 12:
        errors.append("at least 12 characters")
    if sum(1 for c in v if c.isupper()) < 2:
        errors.append("at least 2 uppercase letters")
    if sum(1 for c in v if c.islower()) < 2:
        errors.append("at least 2 lowercase letters")
    if sum(1 for c in v if c.isdigit()) < 2:
        errors.append("at least 2 numbers")
    if sum(1 for c in v if not c.isalnum()) < 2:
        errors.append("at least 2 special characters")
    if errors:
        raise ValueError("Password must contain " + ", ".join(errors))
    return v


class SetApiPasswordRequest(BaseModel):
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_strength(cls, v: str) -> str:
        return _check_password_strength(v)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


class PasswordTokenRequest(BaseModel):
    email: EmailStr
    password: str


# SQLAlchemy models are in app/db/schemas.
# Pydantic models are in app/schemas.


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    email: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

    class Config:
        from_attributes = True


class UserCreate(User):
    password: str


class UserInDB(User):
    hashed_password: str


class SubscriptionResponse(BaseModel):
    status: str
    current_period_end: Optional[datetime.datetime] = None
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class UserSummary(BaseModel):
    id: int
    email: str
    full_name: str | None
    picture: str | None

    class Config:
        from_attributes = True


class PaymentTransactionResponse(BaseModel):
    id: int
    amount: float
    currency: str
    status: str
    event_type: str
    created_at: datetime.datetime
    invoice_url: Optional[str] = None

    class Config:
        from_attributes = True


class AuthUserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    picture: str | None
    is_active: bool
    is_superuser: bool
    last_login: Optional[datetime.datetime] = None
    subscription_status: Optional[str] = None
    subscription: Optional[SubscriptionResponse] = None
    total_spent: float = 0.0
    total_payments: int = 0
    payment_transactions: list[PaymentTransactionResponse] = []

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    picture: str | None
    is_active: bool
    is_superuser: bool
    last_login: Optional[datetime.datetime] = None
    subscription: Optional[SubscriptionResponse] = None
    total_spent: float = 0.0
    total_payments: int = 0
    payment_transactions: list[PaymentTransactionResponse] = []

    class Config:
        from_attributes = True
