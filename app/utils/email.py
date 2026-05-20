from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.config import FRONTEND_URL, GMAIL_APP_PASSWORD, GMAIL_USER, RESET_TOKEN_EXPIRE_MINUTES

_conf = ConnectionConfig(
    MAIL_USERNAME=GMAIL_USER,
    MAIL_PASSWORD=GMAIL_APP_PASSWORD,
    MAIL_FROM=GMAIL_USER,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)


async def send_reset_email(to_email: str, token: str) -> None:
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    message = MessageSchema(
        subject="Reset your BrainRot password",
        recipients=[to_email],
        body=(
            f"Hi,\n\n"
            f"Click the link below to reset your password:\n{reset_link}\n\n"
            f"This link expires in {RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
            f"If you did not request this, ignore this email."
        ),
        subtype=MessageType.plain,
    )
    await FastMail(_conf).send_message(message)
