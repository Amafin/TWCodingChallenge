from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional

class UserAuth(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class PromptBase(BaseModel):
    title: str
    tag: Optional[str] = "Général"
    content: str

class PromptCreate(PromptBase):
    pass

class PromptUpdate(BaseModel):
    title: Optional[str] = None
    tag: Optional[str] = None
    content: Optional[str] = None

class PromptResponse(PromptBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True