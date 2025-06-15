from typing import Optional

from pydantic import BaseModel, EmailStr


# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None


# Properties to receive on user creation
class UserCreate(UserBase):
    email: EmailStr
    password: str


# Properties to receive on user update
class UserUpdate(UserBase):
    password: Optional[str] = None


# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False

    class Config:
        orm_mode = True


# Properties to return to client
class User(UserInDBBase):
    pass


# Properties properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str