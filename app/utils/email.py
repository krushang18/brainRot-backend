import httpx

from app.config import (
    BREVO_API_KEY,
    BREVO_FROM_EMAIL,
    BREVO_FROM_NAME,
    FRONTEND_URL,
    OTP_EXPIRE_MINUTES,
    RESET_TOKEN_EXPIRE_MINUTES,
)


async def _send(to_email: str, subject: str, body: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
            json={
                "sender": {"email": BREVO_FROM_EMAIL, "name": BREVO_FROM_NAME},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body,
            },
        )


async def send_reset_email(to_email: str, token: str) -> None:
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    await _send(
        to_email,
        "Reset your BrainRot password",
        f"Hi,\n\n"
        f"Click the link below to reset your password:\n{reset_link}\n\n"
        f"This link expires in {RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
        f"If you did not request this, ignore this email.",
    )


async def send_otp_email(to_email: str, otp: str) -> None:
    await _send(
        to_email,
        "Your BrainRot login code",
        f"Hi,\n\n"
        f"Your one-time login code is: {otp}\n\n"
        f"This code expires in {OTP_EXPIRE_MINUTES} minutes.\n"
        f"If you did not attempt to log in, please change your password immediately.",
    )
