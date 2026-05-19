from fastapi import APIRouter, HTTPException

from app.schemas.user_schema import SignupRequest
from app.utils.security import hash_password

router = APIRouter()


@router.post("/signup")
def signup(user: SignupRequest):

    if user.password != user.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Passwords do not match"
        )

    hashed_password = hash_password(user.password)

    return {
        "message": "Signup successful",
        "full_name": user.full_name,
        "email": user.email,
        "hashed_password": hashed_password
    }