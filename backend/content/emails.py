"""Email for public contact form submissions.

Mirrors ``bookings.emails``: branding comes from the CMS, transport errors are
logged and swallowed so a broken mail server never turns a delivered enquiry
into a failed form submission.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def notification_recipient():
    """Where contact enquiries are delivered.

    ``CONTACT_NOTIFICATION_EMAIL`` wins, then the booking notification mailbox
    (the site owner's inbox), then the public contact address from Site settings.
    """
    explicit = getattr(settings, 'CONTACT_NOTIFICATION_EMAIL', '') or ''
    if explicit.strip():
        return explicit.strip()

    fallback = getattr(settings, 'BOOKING_NOTIFICATION_EMAIL', '') or ''
    if fallback.strip():
        return fallback.strip()

    from content.models import SiteSettings

    try:
        return (SiteSettings.load().contact_email or '').strip()
    except Exception:  # pragma: no cover - unseeded database
        return ''


def send_contact_message_notice(message, request=None):
    """Deliver a contact form submission to the site's inbox."""
    recipient = notification_recipient()
    if not recipient:
        logger.warning('Contact message %s not emailed — no notification address configured.', message.pk)
        return False

    from content.models import SiteSettings

    try:
        site = SiteSettings.load()
    except Exception:  # pragma: no cover - unseeded database
        site = None

    context = {
        'message': message,
        'site': site,
        'site_title': getattr(site, 'site_title', '') or settings.SITE_NAME,
        'support_email': getattr(site, 'contact_email', '') or settings.DEFAULT_FROM_EMAIL,
        'support_phone': getattr(site, 'contact_phone', '') or '',
        'frontend_url': settings.FRONTEND_URL,
        'admin_url': (
            request.build_absolute_uri(f'/admin/content/contactmessage/{message.pk}/change/')
            if request is not None and message.pk
            else ''
        ),
    }

    try:
        email = EmailMultiAlternatives(
            subject=f'New contact message — {message.subject}',
            body=render_to_string('emails/contact_message.txt', context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
            # Replying in the mail client answers the guest directly.
            reply_to=[message.email],
        )
        email.attach_alternative(render_to_string('emails/contact_message.html', context), 'text/html')
        email.send(fail_silently=False)
    except Exception as error:  # noqa: BLE001 - never lose an enquiry over SMTP
        logger.error('Could not email contact message %s to %s: %s', message.pk, recipient, error)
        return False

    logger.info('Contact message %s emailed to %s', message.pk, recipient)
    return True
