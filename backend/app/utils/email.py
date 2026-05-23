from email.mime.text import MIMEText
import smtplib

from app.core.config import (
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_TLS,
)


def send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    if purpose == "signup":
        subject = "Verify your LMS account"
        heading = "Complete your signup"
    elif purpose == "password_reset":
        subject = "Reset your LMS password"
        heading = "Password reset verification"
    else:
        subject = "Your LMS login OTP"
        heading = "Login verification"

    body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #111827;">
      <h2>{heading}</h2>
      <p>Your OTP is:</p>
      <p style="font-size: 28px; font-weight: 700; letter-spacing: 4px;">{otp}</p>
      <p>This OTP will expire soon. Do not share it with anyone.</p>
    </div>
    """

    if not SMTP_HOST or not SMTP_USERNAME or not SMTP_PASSWORD:
        raise RuntimeError("SMTP is not configured")

    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_USE_TLS:
            server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM_EMAIL, [to_email], msg.as_string())
