from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

def send_otp_email(user, otp_code):
    """
    Sends a verification OTP email to the user using templates.
    """
    subject = 'Verify Your Email - Slash'
    from_email = settings.DEFAULT_FROM_EMAIL
    to = user.email

    context = {
        'user': user,
        'otp_code': otp_code,
    }

    html_content = render_to_string('authentication/email/otp.html', context)
    text_content = render_to_string('authentication/email/otp.txt', context)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def send_kyc_status_email(user, status, notes=None):
    """
    Sends an email notification to the user about their KYC status change.
    """
    subject = f'KYC Verification Update: {status} - Slash'
    from_email = settings.DEFAULT_FROM_EMAIL
    to = user.email

    context = {
        'user': user,
        'status': status,
        'notes': notes,
    }

    html_content = render_to_string('authentication/email/kyc_status.html', context)
    text_content = render_to_string('authentication/email/kyc_status.txt', context)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def send_change_email_otp(user, new_email, otp_code):
    """
    Sends a confirmation OTP to the new email address the user wants to switch to.
    """
    subject = 'Confirm Your New Email Address - Slash'
    from_email = settings.DEFAULT_FROM_EMAIL
    to = new_email

    context = {
        'user': user,
        'otp_code': otp_code,
    }

    html_content = render_to_string('authentication/email/change_email.html', context)
    text_content = render_to_string('authentication/email/change_email.txt', context)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def send_forgot_password_email(user, otp_code):
    """
    Sends a password-reset OTP to the user's registered email address.
    """
    subject = 'Reset Your Password - Slash'
    from_email = settings.DEFAULT_FROM_EMAIL
    to = user.email

    context = {
        'user': user,
        'otp_code': otp_code,
    }

    html_content = render_to_string('authentication/email/forgot_password.html', context)
    text_content = render_to_string('authentication/email/forgot_password.txt', context)

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to])
    msg.attach_alternative(html_content, "text/html")
    msg.send()
