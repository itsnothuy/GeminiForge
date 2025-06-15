from typing import Optional

from pydantic import BaseModel


class TokenBase(BaseModel):
    access_token: str
    token_type: str


class Token(TokenBase):
    pass


class TokenPayload(BaseModel):
    sub: Optional[str] = None