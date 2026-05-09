from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    status: str
    totp_uri: str
    message: str


class SetupConfirmRequest(BaseModel):
    email: EmailStr
    totp_code: str


class AuthRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str


class OkResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    status: str
    message: str
