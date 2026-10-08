from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from core.utils import generate_booking_reference, nights_between


class Booking(TimeStampedModel):
    """A room reservation made by a customer."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CHECKED_IN = 'checked_in', 'Checked in'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    #: Statuses that consume inventory for a date range.
    BLOCKING_STATUSES = (Status.PENDING, Status.CONFIRMED, Status.CHECKED_IN)

    reference = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings'
    )
    room = models.ForeignKey('hotels.Room', on_delete=models.PROTECT, related_name='bookings')
    #: The promotion applied to this stay, when booked through an offer. The
    #: discount is resolved and applied on the server; the client never sets the
    #: price directly.
    offer = models.ForeignKey(
        'offers.Offer', on_delete=models.SET_NULL, null=True, blank=True, related_name='bookings'
    )

    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1)])
    rooms_count = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    nights = models.PositiveSmallIntegerField(default=1, editable=False)

    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), editable=False)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), editable=False)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'), editable=False)

    class PaymentStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Unpaid'
        PARTIALLY_PAID = 'partially_paid', 'Partially Paid'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True
    )
    special_requests = models.TextField(blank=True)

    guest_name = models.CharField(max_length=160)
    guest_email = models.EmailField()
    guest_phone = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        indexes = [models.Index(fields=['check_in', 'check_out'])]

    def __str__(self):
        return f'{self.reference} — {self.room} ({self.check_in} → {self.check_out})'

    # -- pricing ---------------------------------------------------------
    def calculate_totals(self):
        site = None
        try:
            from content.models import SiteSettings

            site = SiteSettings.load()
        except Exception:  # pragma: no cover - during migrations
            site = None

        nights = nights_between(self.check_in, self.check_out) or 1
        nightly = self.price_per_night or self.room.price_per_night
        subtotal = Decimal(nightly) * nights * max(self.rooms_count, 1)
        tax_rate = Decimal(getattr(site, 'tax_percentage', 0) or 0) / Decimal('100')
        tax_amount = (subtotal * tax_rate).quantize(Decimal('0.01'))
        return nights, nightly, subtotal, tax_amount, subtotal + tax_amount

    def save(self, *args, **kwargs):
        if not self.reference:
            reference = generate_booking_reference()
            while Booking.objects.filter(reference=reference).exists():
                reference = generate_booking_reference()
            self.reference = reference

        if not self.price_per_night and self.room_id:
            self.price_per_night = self.room.price_per_night

        nights, nightly, subtotal, tax_amount, total = self.calculate_totals()
        self.nights = nights
        self.price_per_night = nightly
        self.subtotal = subtotal
        self.tax_amount = tax_amount
        self.total_price = total
        super().save(*args, **kwargs)

    # -- helpers ---------------------------------------------------------
    @property
    def hotel(self):
        return self.room.hotel

    @property
    def is_active_stay(self):
        return self.status in self.BLOCKING_STATUSES

    @property
    def can_be_cancelled(self):
        return self.status in (self.Status.PENDING, self.Status.CONFIRMED)


class Payment(TimeStampedModel):
    """Payment record linked to a booking (Razorpay or Cash)."""

    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PARTIALLY_PAID = 'partially_paid', 'Partially Paid'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name='payment'
    )
    provider = models.CharField(max_length=30, default='razorpay')
    order_id = models.CharField(max_length=120, unique=True, blank=True)
    payment_id = models.CharField(max_length=120, blank=True)
    signature = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    cash_received = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
    )
    currency = models.CharField(max_length=8, default='INR')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CREATED, db_index=True
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'

    def __str__(self):
        return f'{self.order_id} — {self.amount} {self.currency} ({self.get_status_display()})'

    @property
    def cash_remaining(self):
        received = self.cash_received or Decimal('0')
        return max(Decimal('0'), self.amount - received)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        received = self.cash_received or Decimal('0')
        if received < Decimal('0'):
            raise ValidationError({'cash_received': 'Cash received cannot be negative.'})

        if self.amount is not None and received > self.amount:
            raise ValidationError(
                {'cash_received': f'Cash received (₹{received:.2f}) cannot exceed total payment amount (₹{self.amount:.2f}).'}
            )

    def save(self, *args, **kwargs):
        if not self.order_id and self.provider == 'cash' and self.booking_id:
            self.order_id = f'CASH-{self.booking.reference}'

        self.full_clean()

        if self.provider == 'cash':
            received = self.cash_received or Decimal('0')
            if received >= self.amount and self.amount > Decimal('0'):
                self.status = Payment.Status.PAID
                if not self.paid_at:
                    self.paid_at = timezone.now()
            elif received > Decimal('0'):
                self.status = Payment.Status.PARTIALLY_PAID
                self.paid_at = None
            else:
                self.status = Payment.Status.CREATED
                self.paid_at = None

        super().save(*args, **kwargs)

        if self.booking_id:
            status_map = {
                Payment.Status.PAID: Booking.PaymentStatus.PAID,
                Payment.Status.PARTIALLY_PAID: Booking.PaymentStatus.PARTIALLY_PAID,
                Payment.Status.REFUNDED: Booking.PaymentStatus.REFUNDED,
            }
            new_payment_status = status_map.get(self.status, Booking.PaymentStatus.UNPAID)
            if self.booking.payment_status != new_payment_status:
                self.booking.payment_status = new_payment_status
                self.booking.save(update_fields=['payment_status', 'updated_at'])


