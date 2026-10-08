"""Hotel deals & promotions.

An :class:`Offer` is a *promotion* attached to an existing hotel (and optionally
a set of its rooms). It never duplicates hotel or room data — it points at the
`hotels` app — and it derives its prices from the room rates that already drive
the booking engine, so an offer can never drift away from real pricing.
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from core.models import (
    ImageAsset,
    OrderedModel,
    SingletonModel,
    TimeStampedModel,
    media_upload_path,
)
from core.utils import nights_between

CENT = Decimal('0.01')
HUNDRED = Decimal('100')


def money(value):
    """Round a decimal to 2dp using normal half-up rounding."""
    return Decimal(value or 0).quantize(CENT, rounding=ROUND_HALF_UP)


class OfferCategory(OrderedModel, TimeStampedModel):
    """A public filter chip such as *Limited Time*, *Early Bird* or *Weekend*.

    Editing the list in the admin changes the chips on the Offers page — nothing
    is hard-coded on the frontend.
    """

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(
        max_length=60, blank=True,
        help_text='Optional icon keyword (e.g. clock, sun, users, tag).',
    )

    class Meta(OrderedModel.Meta):
        verbose_name = 'Offer category'
        verbose_name_plural = 'Offer categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:80] or 'category'
            slug = base
            counter = 1
            while OfferCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f'{base}-{counter}'
            self.slug = slug
        super().save(*args, **kwargs)


class OfferSettings(SingletonModel, TimeStampedModel):
    """Everything the public Offers page renders above the cards.

    A single row, edited from the admin, so headings and the hero can change
    without a deploy. This mirrors the Contact page's settings singleton.
    """

    CACHE_KEY = 'offer_settings'

    # --- Page header / hero ---------------------------------------------
    page_title = models.CharField(max_length=160, default='Offers & Deals')
    page_description = models.TextField(
        blank=True,
        default='Exclusive hotel deals and special rates for your next stay.',
        help_text='Shown under the page title.',
    )
    hero_enabled = models.BooleanField(default=True, verbose_name='Show the Offers hero')
    hero_image = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    hero_image_url = models.URLField(max_length=500, blank=True, help_text='Used when no file is uploaded above.')
    hero_search_enabled = models.BooleanField(
        default=True, verbose_name='Show the destination / dates / guests search',
    )

    # --- Section headings ------------------------------------------------
    featured_enabled = models.BooleanField(default=True, verbose_name='Show featured offers')
    featured_heading = models.CharField(max_length=160, blank=True, default='Featured Offers')
    featured_subheading = models.CharField(
        max_length=255, blank=True, default='Handpicked deals for your next getaway',
    )
    limited_enabled = models.BooleanField(default=True, verbose_name='Show limited-time deals')
    limited_heading = models.CharField(max_length=160, blank=True, default='Limited-Time Deals')
    limited_subheading = models.CharField(
        max_length=255, blank=True, default='Book before these offers expire.',
    )
    limited_window_days = models.PositiveSmallIntegerField(
        default=7, help_text='“Ending soon” window, in days.',
    )

    # --- SEO -------------------------------------------------------------
    seo_title = models.CharField(max_length=160, blank=True, default='Hotel Offers & Deals | SkyStay')
    seo_description = models.TextField(
        blank=True,
        default='Save on your next stay with exclusive hotel deals, seasonal packages and limited-time promotions.',
    )

    class Meta:
        verbose_name = 'Offers page settings'
        verbose_name_plural = 'Offers page settings'

    def __str__(self):
        return self.page_title or 'Offers page settings'


class OfferQuerySet(models.QuerySet):
    def live(self, today=None):
        """Only offers that are published, enabled and inside their validity window."""
        today = today or timezone.localdate()
        return self.filter(
            is_published=True,
            is_disabled=False,
            start_date__lte=today,
            end_date__gte=today,
        )

    def featured(self, today=None):
        return self.live(today=today).filter(is_featured=True)

    def ending_soon(self, days=7, today=None):
        today = today or timezone.localdate()
        return self.live(today=today).filter(end_date__lte=today + timedelta(days=days))


class Offer(TimeStampedModel):
    """A discount / package attached to one hotel (and optionally some rooms)."""

    class OfferType(models.TextChoices):
        SEASONAL = 'seasonal', 'Seasonal'
        WEEKEND = 'weekend', 'Weekend'
        EARLY_BIRD = 'early_bird', 'Early Bird'
        LONG_STAY = 'long_stay', 'Long Stay'
        LAST_MINUTE = 'last_minute', 'Last Minute'
        COUPLES = 'couples', 'Couples'
        FAMILY = 'family', 'Family'
        LUXURY = 'luxury', 'Luxury'
        PACKAGE = 'package', 'Package'
        OTHER = 'other', 'Other'

    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', 'Percentage Discount'
        FIXED = 'fixed', 'Fixed Amount Discount'
        SPECIAL_PRICE = 'special_price', 'Special Price'
        FREE_NIGHT = 'free_night', 'Free Night'
        PACKAGE = 'package', 'Package Deal'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        ACTIVE = 'active', 'Active'
        EXPIRED = 'expired', 'Expired'
        DISABLED = 'disabled', 'Disabled'

    # --- Identity --------------------------------------------------------
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True, help_text='Long description shown on the offer page.')

    # --- Relationships (never duplicate hotels/rooms) --------------------
    category = models.ForeignKey(
        OfferCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='offers',
    )
    hotel = models.ForeignKey('hotels.Hotel', on_delete=models.CASCADE, related_name='offers')
    rooms = models.ManyToManyField(
        'hotels.Room', blank=True, related_name='offers',
        help_text='Leave empty to apply the offer to every eligible room in the hotel.',
    )

    # --- Classification --------------------------------------------------
    offer_type = models.CharField(
        max_length=20, choices=OfferType.choices, default=OfferType.SEASONAL, db_index=True,
    )

    # --- Discount / pricing ---------------------------------------------
    discount_type = models.CharField(
        max_length=20, choices=DiscountType.choices, default=DiscountType.PERCENTAGE,
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text='Percentage for a % discount, amount for a fixed discount, nightly price for a special price.',
    )
    free_nights = models.PositiveSmallIntegerField(
        default=0, help_text='Nights given free (free-night offers only).',
    )
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Optional displayed “was” price. Leave empty to use the cheapest eligible room rate.',
    )

    # --- Validity --------------------------------------------------------
    start_date = models.DateField()
    end_date = models.DateField()

    # --- Restrictions ----------------------------------------------------
    min_stay = models.PositiveSmallIntegerField(default=1, help_text='Minimum nights required.')
    max_stay = models.PositiveSmallIntegerField(
        default=0, help_text='Maximum nights allowed. 0 means no limit.',
    )
    min_booking_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        help_text='Optional minimum booking subtotal.',
    )
    blackout_start = models.DateField(null=True, blank=True, help_text='Optional blackout window start.')
    blackout_end = models.DateField(null=True, blank=True, help_text='Optional blackout window end.')

    # --- Promo -----------------------------------------------------------
    promo_code_enabled = models.BooleanField(default=False)
    promo_code = models.CharField(max_length=40, blank=True)

    # --- Terms -----------------------------------------------------------
    terms = models.TextField(blank=True, help_text='One term per line.')

    # --- Media -----------------------------------------------------------
    image = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, help_text='Used when no file is uploaded above.')

    # --- Publishing ------------------------------------------------------
    is_featured = models.BooleanField(default=False, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    is_disabled = models.BooleanField(
        default=False, help_text='Manually take the offer offline without deleting it.',
    )
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    # --- Analytics (lightweight counters, safe to grow) ------------------
    view_count = models.PositiveIntegerField(default=0, editable=False)
    click_count = models.PositiveIntegerField(default=0, editable=False)
    booking_count = models.PositiveIntegerField(default=0, editable=False)

    objects = OfferQuerySet.as_manager()

    class Meta:
        ordering = ['display_order', '-is_featured', '-created_at']
        verbose_name = 'Offer'
        verbose_name_plural = 'Offers'
        indexes = [models.Index(fields=['start_date', 'end_date'])]

    def __str__(self):
        return f'{self.title} — {self.hotel.name}'

    # -- slugs ------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or 'offer'
            slug = base
            counter = 1
            while Offer.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f'{base}-{counter}'
            self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.end_date < self.start_date:
            errors['end_date'] = 'The end date must be on or after the start date.'
        if self.discount_type in (self.DiscountType.PERCENTAGE, self.DiscountType.FIXED) and (
            self.discount_value or 0
        ) <= 0:
            errors['discount_value'] = 'Enter a discount value greater than zero.'
        if self.discount_type == self.DiscountType.PERCENTAGE and (self.discount_value or 0) > 100:
            errors['discount_value'] = 'A percentage discount cannot exceed 100%.'
        if self.discount_type == self.DiscountType.FREE_NIGHT and (self.free_nights or 0) < 1:
            errors['free_nights'] = 'Set at least one free night for a free-night offer.'
        if self.promo_code_enabled and not self.promo_code.strip():
            errors['promo_code'] = 'Enter the promo code or uncheck “Promo code enabled”.'
        if (self.blackout_start is None) != (self.blackout_end is None):
            errors['blackout_end'] = 'Set both blackout dates, or leave both empty.'
        elif self.blackout_start and self.blackout_end and self.blackout_end < self.blackout_start:
            errors['blackout_end'] = 'The blackout end date must be on or after the blackout start.'
        if errors:
            raise ValidationError(errors)

    # -- status -----------------------------------------------------------
    def compute_status(self, today=None):
        if not self.is_published:
            return self.Status.DRAFT
        if self.is_disabled:
            return self.Status.DISABLED
        today = today or timezone.localdate()
        if self.start_date and today < self.start_date:
            return self.Status.SCHEDULED
        if self.end_date and today > self.end_date:
            return self.Status.EXPIRED
        return self.Status.ACTIVE

    @property
    def status(self):
        return self.compute_status()

    @property
    def status_label(self):
        return self.Status(self.status).label

    @property
    def is_live(self):
        return self.status == self.Status.ACTIVE

    @property
    def is_expired(self):
        return self.status == self.Status.EXPIRED

    @property
    def days_until_end(self):
        if not self.end_date:
            return None
        return (self.end_date - timezone.localdate()).days

    def ends_within(self, days):
        remaining = self.days_until_end
        return remaining is not None and 0 <= remaining <= days

    # -- rooms ------------------------------------------------------------
    def applicable_rooms(self):
        """Rooms the offer covers, falling back to every active room in the hotel."""
        rooms = [room for room in self.rooms.all() if room.is_active]
        if rooms:
            return rooms
        return [room for room in self.hotel.rooms.all() if room.is_active]

    def room_is_eligible(self, room):
        if room is None or room.hotel_id != self.hotel_id:
            return False
        explicit = [r for r in self.rooms.all()]
        if explicit:
            return any(r.pk == room.pk for r in explicit)
        return room.is_active

    # -- pricing ----------------------------------------------------------
    @property
    def base_price(self):
        """The “was” price: the admin override, else the cheapest eligible rate."""
        if self.original_price is not None:
            return money(self.original_price)
        rooms = self.applicable_rooms()
        if rooms:
            return money(min(room.price_per_night for room in rooms))
        return money(self.hotel.price_per_night or 0)

    def _apply_discount(self, base):
        base = Decimal(base or 0)
        value = Decimal(self.discount_value or 0)
        if self.discount_type == self.DiscountType.PERCENTAGE:
            price = base - (base * value / HUNDRED)
        elif self.discount_type == self.DiscountType.FIXED:
            price = base - value
        elif self.discount_type in (self.DiscountType.SPECIAL_PRICE, self.DiscountType.PACKAGE):
            price = value if value > 0 else base
        else:  # FREE_NIGHT — the nightly rate is unchanged; a night is given free.
            price = base
        return money(max(price, Decimal('0')))

    def nightly_price_for(self, room=None):
        """Server-side nightly price for a room (or the offer's base) after discount."""
        if room is not None:
            return self._apply_discount(room.price_per_night)
        return self._apply_discount(self.base_price)

    @property
    def offer_price(self):
        return self.nightly_price_for()

    @property
    def saving(self):
        return money(max(self.base_price - self.offer_price, Decimal('0')))

    @property
    def discount_percent(self):
        base = self.base_price
        if base <= 0:
            return 0
        return int(round(float((base - self.offer_price) / base) * 100))

    # -- validation -------------------------------------------------------
    def validate_stay(self, check_in, check_out):
        """Return a list of human-readable problems with a proposed stay."""
        errors = []
        if not check_in or not check_out:
            return ['Select both a check-in and a check-out date.']
        if check_out <= check_in:
            return ['Check-out must be after check-in.']
        if self.start_date and check_in < self.start_date:
            errors.append(f'This offer is only valid for stays from {self.start_date:%b %d, %Y}.')
        if self.end_date and check_out > self.end_date:
            errors.append(f'This offer is only valid for stays until {self.end_date:%b %d, %Y}.')

        nights = nights_between(check_in, check_out)
        if self.min_stay and nights < self.min_stay:
            errors.append(f'This offer requires a minimum stay of {self.min_stay} night(s).')
        if self.max_stay and nights > self.max_stay:
            errors.append(f'This offer allows a maximum stay of {self.max_stay} night(s).')

        if self.blackout_start and self.blackout_end and check_in <= self.blackout_end and check_out >= self.blackout_start:
            errors.append(
                f'This offer cannot be booked for stays between '
                f'{self.blackout_start:%b %d} and {self.blackout_end:%b %d}.'
            )
        return errors

    def terms_list(self):
        return [line.strip() for line in (self.terms or '').splitlines() if line.strip()]


class OfferBenefit(OrderedModel, TimeStampedModel):
    """A repeatable, reorderable “what's included” line (Breakfast, WiFi, ...)."""

    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='benefits')
    text = models.CharField(max_length=160)
    icon = models.CharField(max_length=60, blank=True, help_text='Optional icon keyword.')

    class Meta(OrderedModel.Meta):
        verbose_name = 'Offer benefit'
        verbose_name_plural = 'Offer benefits'

    def __str__(self):
        return self.text


class OfferImage(ImageAsset):
    """Gallery image attached to an offer."""

    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='images')

    class Meta(ImageAsset.Meta):
        verbose_name = 'Offer image'
        verbose_name_plural = 'Offer images'

    def __str__(self):
        return f'{self.offer.title} — {super().__str__()}'
