from pydantic import BaseModel, EmailStr


class UserInDB(BaseModel):
    full_name: str
    email: EmailStr
    hashed_password: str
