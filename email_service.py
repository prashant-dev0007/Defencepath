"""
DEFENCE PATH - Secure Email & Notification Service
Handles cryptographic OTP transmission for First-Time Setup and Password Recovery.
Configuration is sourced securely from environment variables / .env file.
"""

import os
import smtplib
import ssl
from email.message import EmailMessage
import logging
from dotenv import load_dotenv

# Load environment configuration if present
load_dotenv()

logger = logging.getLogger("defence_path.email")

def get_smtp_config():
    return {
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "use_tls": os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"),
        "use_ssl": os.environ.get("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes"),
        "user": os.environ.get("SMTP_USER", "").strip(),
        "password": os.environ.get("SMTP_PASSWORD", "").strip(),
        "from_email": os.environ.get("SMTP_FROM_EMAIL", "").strip() or os.environ.get("SMTP_USER", "").strip() or "noreply@defencepath.in",
        "from_name": os.environ.get("SMTP_FROM_NAME", "DEFENCE PATH Command").strip()
    }

def is_smtp_configured():
    config = get_smtp_config()
    return bool(config["host"] and config["user"] and config["password"])

def send_otp_email(recipient_email, otp_code, purpose="Password Recovery", recipient_name="Cadet"):
    """
    Transmits a secure 6-digit OTP code to the recipient email address.
    Returns (success: bool, message: str).
    Never exposes credentials or raw server errors to the user.
    """
    config = get_smtp_config()
    
    if not is_smtp_configured():
        logger.warning("SMTP configuration is incomplete. Cannot send email OTP.")
        return False, "Email delivery service is currently not configured on this server. Please contact system administrator."

    try:
        msg = EmailMessage()
        msg['Subject'] = f"[DEFENCE PATH] Security Verification Code: {otp_code}"
        msg['From'] = f"{config['from_name']} <{config['from_email']}>"
        msg['To'] = recipient_email

        # Plain-Text Version
        text_content = f"""
=====================================================
DEFENCE PATH - ARMED FORCES PORTAL
"Your Dream. Your Discipline. Your Uniform."
=====================================================

Hello {recipient_name},

A security request has been initiated for: {purpose}
Account Email: {recipient_email}

YOUR ONE-TIME VERIFICATION CODE:
{otp_code}

* Security Notice:
- This code is valid for exactly 5 MINUTES.
- This code can only be used once.
- Never share this code with anyone, including DEFENCE PATH staff.
- If you did not request this verification, please ignore this email or review your account security.

Best regards,
DEFENCE PATH Security Command
Er. Prashant Mishra | Lead Architect
        """.strip()

        # HTML Version (Military Green / Gold Accent Theme matching platform UI)
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #050c08;
      color: #e2e8f0;
      margin: 0;
      padding: 24px;
    }}
    .card {{
      max-width: 520px;
      margin: 0 auto;
      background-color: #0c1610;
      border: 1px solid #1f3627;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }}
    .header {{
      background: linear-gradient(135deg, #09130d 0%, #122218 100%);
      padding: 24px;
      text-align: center;
      border-bottom: 2px solid #d97706;
    }}
    .badge {{
      display: inline-block;
      background: rgba(217, 119, 6, 0.2);
      color: #fbbf24;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 2px;
      text-transform: uppercase;
      padding: 4px 12px;
      border-radius: 9999px;
      border: 1px solid rgba(217, 119, 6, 0.4);
      margin-bottom: 8px;
    }}
    .title {{
      font-size: 22px;
      font-weight: 800;
      color: #ffffff;
      margin: 0;
      letter-spacing: 1px;
    }}
    .subtitle {{
      font-size: 11px;
      color: #94a3b8;
      margin-top: 4px;
    }}
    .content {{
      padding: 28px 24px;
    }}
    .otp-box {{
      margin: 20px 0;
      background-color: #122218;
      border: 2px dashed #f59e0b;
      border-radius: 10px;
      padding: 16px;
      text-align: center;
    }}
    .otp-code {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 32px;
      font-weight: 800;
      letter-spacing: 8px;
      color: #fbbf24;
    }}
    .otp-expiry {{
      font-size: 12px;
      color: #94a3b8;
      margin-top: 6px;
    }}
    .footer {{
      padding: 16px 24px;
      background-color: #080f0a;
      border-top: 1px solid #1a2e21;
      font-size: 11px;
      color: #64748b;
      text-align: center;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="badge">SECURE VERIFICATION GATEWAY</div>
      <h1 class="title">DEFENCE PATH</h1>
      <div class="subtitle">"Your Dream. Your Discipline. Your Uniform."</div>
    </div>
    <div class="content">
      <p style="font-size: 14px; color: #cbd5e1; margin-top: 0;">
        Hello <strong>{recipient_name}</strong>,
      </p>
      <p style="font-size: 13px; color: #94a3b8; line-height: 1.5;">
        A security verification request has been initiated for <strong>{purpose}</strong> on your DEFENCE PATH account (<em>{recipient_email}</em>).
      </p>
      <div class="otp-box">
        <div class="otp-code">{otp_code}</div>
        <div class="otp-expiry">Valid for 5 minutes &bull; Single-use only</div>
      </div>
      <p style="font-size: 12px; color: #94a3b8; line-height: 1.5;">
        Please enter this 6-digit code in the verification screen to proceed. If you did not initiate this request, no further action is required; your account remains secure.
      </p>
    </div>
    <div class="footer">
      Defence Path Armed Forces Portal &bull; System Architect: Er. Prashant Mishra &bull; 6390314464
    </div>
  </div>
</body>
</html>
        """.strip()

        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype='html')

        if config["use_ssl"]:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config["host"], config["port"], context=context, timeout=12) as server:
                server.login(config["user"], config["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(config["host"], config["port"], timeout=12) as server:
                if config["use_tls"]:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                server.login(config["user"], config["password"])
                server.send_message(msg)

        logger.info(f"Verification email successfully dispatched to {recipient_email}")
        return True, "Verification email dispatched successfully."

    except Exception as e:
        logger.error(f"Failed to transmit email: {e}")
        return False, "Failed to deliver verification email. Please verify SMTP server settings or try again later."
