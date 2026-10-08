"""Small helpers shared across the API apps."""

import random
import string
from datetime import date
from decimal import Decimal

from django.db.models import Sum


def absolute_media_url(request, file_field):
    """Return an absolute URL for an uploaded media file, or None."""
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:  # pragma: no cover - field without a file
        return None
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def resolve_image(request, uploaded_field, external_url):
    """Prefer an admin-uploaded file, fall back to an external URL.

    This lets the CMS work with either uploaded media or remote imagery, which
    keeps the seeded demo content functional without shipping binary assets.
    """
    uploaded = absolute_media_url(request, uploaded_field)
    if uploaded:
        return uploaded
    return external_url or None


def generate_booking_reference():
    """Human friendly, collidable-resistant booking reference e.g. SKY-7F3K9A."""
    alphabet = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(alphabet, k=6))
    return f'SKY-{suffix}'


def nights_between(check_in, check_out):
    """Number of billable nights, minimum 1."""
    if not check_in or not check_out:
        return 0
    delta = (check_out - check_in).days
    return max(delta, 0)


def booked_rooms_for_range(room, check_in, check_out, exclude_booking=None):
    """How many rooms of this type are already reserved over an overlapping range.

    A single booking can hold several rooms (``rooms_count``), so the inventory
    must be summed rather than counted.
    """
    from bookings.models import Booking

    overlapping = Booking.objects.filter(
        room=room,
        status__in=Booking.BLOCKING_STATUSES,
        check_in__lt=check_out,
        check_out__gt=check_in,
    )
    if exclude_booking is not None and exclude_booking.pk:
        overlapping = overlapping.exclude(pk=exclude_booking.pk)
    return overlapping.aggregate(total=Sum('rooms_count'))['total'] or 0


def room_availability_for_range(room, check_in, check_out, exclude_booking=None):
    """Return (is_available, rooms_left) for a room across a date range."""
    if not check_in or not check_out or check_out <= check_in:
        return room.total_rooms > 0, room.total_rooms
    used = booked_rooms_for_range(room, check_in, check_out, exclude_booking)
    left = max(room.total_rooms - used, 0)
    return left > 0, left


def money(value):
    """Format a numeric value as a fixed 2dp string.

    Aggregates over ``DecimalField`` come back as ``Decimal`` on MySQL but as
    ``float`` on SQLite, so normalise before exposing the value through the API.
    """
    return f'{Decimal(str(value if value is not None else 0)):.2f}'


def parse_date(value):
    """Parse an ISO ``YYYY-MM-DD`` string, returning None when invalid."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None
