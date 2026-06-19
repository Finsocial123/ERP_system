from email.mime.text import MIMEText
from html import escape
import smtplib

from app.core.config import settings


class EmailNotConfiguredError(RuntimeError):
    pass


def _smtp_ready() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD and settings.smtp_from_email)


def _send_html_email(to_email: str, subject: str, body: str) -> None:
    if not _smtp_ready():
        raise EmailNotConfiguredError("SMTP is not configured. Add SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM_EMAIL in backend/.env")

    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.smtp_from_email}>"
    msg["To"] = to_email

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.smtp_from_email, [to_email], msg.as_string())


def send_school_registration_otp_email(to_email: str, otp: str, school_name: str) -> None:
    subject = "Verify your school registration"
    body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #111827;">
      <h2>Verify your school / college registration</h2>
      <p>You requested to register <strong>{school_name}</strong> on School ERP.</p>
      <p>Your verification OTP is:</p>
      <p style="font-size: 28px; font-weight: 700; letter-spacing: 4px;">{otp}</p>
      <p>This OTP expires in {settings.OTP_EXPIRE_MINUTES} minutes. Do not share it with anyone.</p>
      <p>If you did not request this, you can ignore this email.</p>
    </div>
    """
    _send_html_email(to_email, subject, body)


def send_password_reset_email(to_email: str, reset_url: str, full_name: str | None = None) -> None:
    subject = "Reset your School ERP password"
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #111827;">
      <h2>Password reset request</h2>
      <p>{greeting}</p>
      <p>We received a request to reset your School ERP password.</p>
      <p>
        <a href="{reset_url}" style="display:inline-block;background:#0f172a;color:#ffffff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:700;">
          Reset Password
        </a>
      </p>
      <p>This link expires in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
      <p>If the button does not work, copy and paste this link into your browser:</p>
      <p style="word-break: break-all; font-size: 13px; color: #334155;">{reset_url}</p>
      <p>If you did not request this, you can safely ignore this email.</p>
    </div>
    """
    _send_html_email(to_email, subject, body)


def send_otp_email(to_email: str, otp: str, purpose: str) -> None:
    """Backward-compatible helper for older code paths."""
    if purpose == "signup":
        send_school_registration_otp_email(to_email, otp, "your institution")
        return

    subject = "Your School ERP verification OTP"
    heading = "Email verification"
    if purpose == "password_reset":
        subject = "Reset your School ERP password"
        heading = "Password reset verification"

    body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #111827;">
      <h2>{heading}</h2>
      <p>Your OTP is:</p>
      <p style="font-size: 28px; font-weight: 700; letter-spacing: 4px;">{otp}</p>
      <p>This OTP will expire soon. Do not share it with anyone.</p>
    </div>
    """
    _send_html_email(to_email, subject, body)



def send_ai_response_email(
    to_email: str,
    subject: str,
    answer: str,
    *,
    lesson_title: str | None = None,
    course_title: str | None = None,
    sent_by: str | None = None,
) -> None:
    """Send an AI tutor answer to a student/teacher email address."""
    safe_answer = escape(answer).replace("\n", "<br>")
    meta_lines = []
    if course_title:
        meta_lines.append(f"<strong>Course:</strong> {escape(course_title)}")
    if lesson_title:
        meta_lines.append(f"<strong>Lesson:</strong> {escape(lesson_title)}")
    if sent_by:
        meta_lines.append(f"<strong>Sent by:</strong> {escape(sent_by)}")

    meta_html = ""
    if meta_lines:
        meta_html = (
            '<div style="margin: 12px 0 18px; padding: 10px 12px; background: #f8fafc; '
            'border: 1px solid #e2e8f0; border-radius: 10px; font-size: 13px; color: #475569;">'
            + "<br>".join(meta_lines)
            + "</div>"
        )

    body = f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #111827;">
      <h2 style="margin: 0 0 8px;">AI Tutor Response</h2>
      <p style="margin: 0; color: #64748b;">Shared from School ERP LMS chat.</p>
      {meta_html}
      <div style="padding: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
        {safe_answer}
      </div>
    </div>
    """
    _send_html_email(to_email, subject, body)
