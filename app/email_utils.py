from flask_mail import Message
from . import mail

def send_email(to, subject, body):
    try:
        msg = Message(subject, recipients=[to])
        msg.body = body
        mail.send(msg)
        print(f"Email sent to {to}")
    except Exception as e:
        print(f"Error sending email: {e}")
