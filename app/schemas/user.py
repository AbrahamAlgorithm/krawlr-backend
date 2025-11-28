from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: str
    name: str
    email: EmailStr

class UserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class TokenRefresh(BaseModel):
    refreshToken: str

class DeleteAccount(BaseModel):
    password: str