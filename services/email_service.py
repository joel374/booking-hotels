import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Email Configuration from Environment Variables
MAIL_SERVER = os.getenv('MAIL_SERVER')
MAIL_PORT = os.getenv('MAIL_PORT', 587)
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@bookinghotels.com')

def send_email(to_email, subject, html_content):
    """
    Sends an email using standard smtplib.
    If SMTP credentials are not configured, it fails fast and does nothing.
    """
    if not MAIL_SERVER or not MAIL_USERNAME or not MAIL_PASSWORD:
        # Mock mode skipped as requested by user
        return False
        
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = MAIL_DEFAULT_SENDER
        msg['To'] = to_email

        # Attach HTML content
        part = MIMEText(html_content, 'html')
        msg.attach(part)

        # Connect to SMTP server
        server = smtplib.SMTP(MAIL_SERVER, int(MAIL_PORT))
        
        if MAIL_USE_TLS:
            server.starttls()
            
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
