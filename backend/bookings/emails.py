"""Transactional email for reservations.

Every message goes through :func:`_send`, which logs and swallows transport
errors — an SMTP outage must never turn a confirmed booking into a 500.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _context(booking, request=None):
    """Template context shared by every reservation email.

    Branding, currency and contact details come from the CMS (Site settings) so
    the mails match whatever the admin has configured.
    """
    from content.models import SiteSettings

    try:
        site = SiteSettings.load()
    except Exception:  # pragma: no cover - unseeded database
        site = None

    room = booking.room
    admin_url = ''
    if request is not None and booking.pk:
        admin_url = request.build_absolute_uri(f'/admin/bookings/booking/{booking.pk}/change/')

    return {
        'booking': booking,
        'room': room,
        'hotel': room.hotel,
        'site': site,
        'site_title': getattr(site, 'site_title', '') or settings.SITE_NAME,
        'currency_symbol': getattr(site, 'currency_symbol', '') or '$',
        'support_email': getattr(site, 'contact_email', '') or settings.DEFAULT_FROM_EMAIL,
        'support_phone': getattr(site, 'contact_phone', '') or '',
        'frontend_url': settings.FRONTEND_URL,
        'admin_url': admin_url,
    }


def _send(subject, recipient, template_stem, context):
    recipient = (recipient or '').strip()
    if not recipient:
        logger.info('Skipping "%s" — no recipient address.', subject)
        return False

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string(f'emails/{template_stem}.txt', context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        message.attach_alternative(
            render_to_string(f'emails/{template_stem}.html', context), 'text/html'
        )
        message.send(fail_silently=False)
    except Exception as error:  # noqa: BLE001 - never break a booking over email
        logger.error('Could not send "%s" to %s: %s', subject, recipient, error)
        return False

    logger.info('Sent "%s" to %s', subject, recipient)
    return True


def send_booking_confirmation(booking, request=None):
    """Receipt for the guest, sent only once the booking is actually paid.

    Called after a verified online payment (or by the front desk). A booking
    that is still awaiting payment must not be announced as confirmed.
    """
    return _send(
        f'Booking confirmed — {booking.reference}',
        booking.guest_email,
        'booking_confirmation',
        _context(booking, request),
    )


def send_booking_reserved(booking, request=None):
    """Cash reservations: the room is held, the money is collected at the desk."""
    return _send(
        f'Booking reserved — {booking.reference} (payment pending)',
        booking.guest_email,
        'booking_reserved',
        _context(booking, request),
    )


def send_booking_cancellation(booking, request=None):
    """Cancellation notice, including the freed-up inventory."""
    return _send(
        f'Booking cancelled — {booking.reference}',
        booking.guest_email,
        'booking_cancelled',
        _context(booking, request),
    )


def send_staff_booking_notice(booking, request=None):
    """Heads-up to the hotel team so the reservation can be confirmed."""
    recipient = settings.BOOKING_NOTIFICATION_EMAIL
    # Self-testing with the mailbox's own address would just duplicate the guest copy.
    if recipient and recipient.strip().lower() == (booking.guest_email or '').strip().lower():
        logger.info('Skipping staff notice for %s — same address as the guest.', booking.reference)
        return False
    return _send(
        f'New booking {booking.reference} — {booking.room.hotel.name}',
        recipient,
        'booking_notice',
        _context(booking, request),
    )
