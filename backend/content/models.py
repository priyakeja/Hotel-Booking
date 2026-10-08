import re

from django.core.exceptions import ValidationError
from django.db import models

from core.models import ImageAsset, OrderedModel, SingletonModel, TimeStampedModel, media_upload_path

# Loose international phone check: digits with the usual spacing/+()- separators,
# at least 7 digits so "+91 98765 43210" passes but "123" does not.
PHONE_RE = re.compile(r'^\+?[0-9][0-9\s().-]{5,}$')


class SiteSettings(SingletonModel, TimeStampedModel):
    """Global branding and contact details edited from the Django admin.

    Everything the header, footer and document head display is sourced here so
    the site can be re-branded without touching code.
    """

    site_title = models.CharField(max_length=120, default='SkyStay')
    tagline = models.CharField(max_length=160, blank=True, help_text='Shown next to the logo.')
    logo = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    logo_url = models.URLField(max_length=500, blank=True, help_text='External fallback logo URL.')
    favicon = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    footer_text = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)

    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    address = models.CharField(max_length=255, blank=True)

    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)

    currency_code = models.CharField(max_length=8, default='INR')
    currency_symbol = models.CharField(max_length=8, default='₹')
    default_check_in_time = models.CharField(max_length=20, default='14:00')
    default_check_out_time = models.CharField(max_length=20, default='11:00')
    tax_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text='Applied on top of the room subtotal when quoting bookings.',
    )

    CACHE_KEY = 'site_settings'

    class Meta:
        verbose_name = 'Site settings'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return self.site_title


class NavLink(OrderedModel, TimeStampedModel):
    """A header or footer navigation entry."""

    class Location(models.TextChoices):
        HEADER = 'header', 'Header'
        FOOTER = 'footer', 'Footer'
        FOOTER_LEGAL = 'footer_legal', 'Footer (legal row)'

    label = models.CharField(max_length=80)
    url = models.CharField(max_length=255, default='/', help_text='Internal path or full URL.')
    location = models.CharField(max_length=20, choices=Location.choices, default=Location.HEADER)
    open_in_new_tab = models.BooleanField(default=False)

    class Meta(OrderedModel.Meta):
        verbose_name = 'Navigation link'
        verbose_name_plural = 'Navigation links'

    def __str__(self):
        return f'{self.label} ({self.get_location_display()})'


class HeroBanner(OrderedModel, TimeStampedModel):
    """Full width homepage banner with background imagery and CTAs."""

    eyebrow = models.CharField(max_length=120, blank=True, help_text='Small text above the title.')
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    background = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    background_url = models.URLField(max_length=500, blank=True)
    overlay_opacity = models.DecimalField(
        max_digits=3, decimal_places=2, default='0.55',
        help_text='Dark overlay strength between 0.00 and 0.90.',
    )
    cta_text = models.CharField(max_length=60, blank=True)
    cta_link = models.CharField(max_length=255, blank=True)
    secondary_cta_text = models.CharField(max_length=60, blank=True)
    secondary_cta_link = models.CharField(max_length=255, blank=True)
    show_search_form = models.BooleanField(default=True)

    class Meta(OrderedModel.Meta):
        verbose_name = 'Hero banner'
        verbose_name_plural = 'Hero banners'

    def __str__(self):
        return self.title


class Feature(OrderedModel, TimeStampedModel):
    """Icon + text highlight, e.g. the trust strip under the hero."""

    icon = models.CharField(
        max_length=60, default='shield',
        help_text='Icon keyword used by the frontend icon set (shield, clock, lock, tag...).',
    )
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = 'Feature'
        verbose_name_plural = 'Features'

    def __str__(self):
        return self.title


class Amenity(OrderedModel, TimeStampedModel):
    """Amenity that can be attached to hotels and rooms."""

    name = models.CharField(max_length=80, unique=True)
    icon = models.CharField(max_length=60, default='check')
    description = models.CharField(max_length=255, blank=True)
    show_on_homepage = models.BooleanField(default=False)

    class Meta(OrderedModel.Meta):
        verbose_name = 'Amenity'
        verbose_name_plural = 'Amenities'

    def __str__(self):
        return self.name


class Testimonial(OrderedModel, TimeStampedModel):
    """Guest review surfaced on the marketing homepage."""

    name = models.CharField(max_length=120)
    location = models.CharField(max_length=120, blank=True)
    message = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    avatar = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    hotel = models.ForeignKey(
        'hotels.Hotel', on_delete=models.SET_NULL, null=True, blank=True, related_name='testimonials'
    )

    class Meta(OrderedModel.Meta):
        verbose_name = 'Testimonial'
        verbose_name_plural = 'Testimonials'

    def __str__(self):
        return f'{self.name} — {self.rating}★'


class TextSection(OrderedModel, TimeStampedModel):
    """Reusable, admin editable block of copy (section headings, CTA bands...)."""

    class Key(models.TextChoices):
        FEATURED_HOTELS = 'featured_hotels', 'Featured hotels section'
        HOTELS_LISTING = 'hotels_listing', 'Hotels listing header'
        AMENITIES = 'amenities', 'Amenities section'
        TESTIMONIALS = 'testimonials', 'Testimonials section'
        ABOUT = 'about', 'About / highlight band'
        CTA = 'cta', 'Call to action band'
        DASHBOARD = 'dashboard', 'Customer dashboard'
        CONTACT = 'contact', 'Contact page'
        PRIVACY = 'privacy', 'Privacy policy page'
        TERMS = 'terms', 'Terms of service page'
        COOKIES = 'cookies', 'Cookie policy page'

    key = models.SlugField(max_length=60, choices=Key.choices, unique=True)
    eyebrow = models.CharField(max_length=120, blank=True)
    heading = models.CharField(max_length=200)
    subheading = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True)
    cta_text = models.CharField(max_length=60, blank=True)
    cta_link = models.CharField(max_length=255, blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = 'Text section'
        verbose_name_plural = 'Text sections'

    def __str__(self):
        return f'{self.get_key_display()}: {self.heading}'


class GalleryImage(ImageAsset):
    """Extra standalone imagery managed from the CMS (about band, CTA, ...)."""

    section = models.ForeignKey(
        TextSection, on_delete=models.CASCADE, null=True, blank=True, related_name='gallery'
    )
    title = models.CharField(max_length=160, blank=True)

    class Meta(ImageAsset.Meta):
        verbose_name = 'Gallery image'
        verbose_name_plural = 'Gallery images'

    def __str__(self):
        return self.title or super().__str__()


class ContactSettings(SingletonModel, TimeStampedModel):
    """Everything the public Contact page renders, edited from the admin.

    Single source of truth for the contact page *and* the footer contact block,
    so changing the phone number in one place updates both. One global record:
    the SkyStay contact page is a company-wide page, not a per-property one.

    For a property-specific location, link ``location_hotel`` to a Hotel — its
    name, address and coordinates then win over the manual fields below, which
    keeps property data in one place instead of duplicating it here.
    """

    CACHE_KEY = 'contact_settings'

    # --- General ---------------------------------------------------------
    page_title = models.CharField(max_length=160, default='Contact us')
    intro_message = models.TextField(
        blank=True, help_text='Short intro shown under the page title.'
    )
    response_time = models.CharField(
        max_length=160, blank=True, help_text='e.g. Our team replies within one business day.'
    )
    intro_enabled = models.BooleanField(default=True, verbose_name='Show the intro alert')

    # --- Contact details -------------------------------------------------
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    support_hours = models.CharField(max_length=120, blank=True, help_text='e.g. 24/7 or Mon–Fri, 9am–6pm.')

    # --- Location --------------------------------------------------------
    location_hotel = models.ForeignKey(
        'hotels.Hotel', on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        help_text='Optional. When set, this property name, address and coordinates are published '
                  'instead of the manual values below.',
    )
    property_name = models.CharField(max_length=160, blank=True, default='SkyStay')
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state_region = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    map_enabled = models.BooleanField(default=True, verbose_name='Show the interactive map')

    # --- Primary actions -------------------------------------------------
    primary_cta_text = models.CharField(max_length=60, blank=True, default='Browse hotels')
    primary_cta_link = models.CharField(max_length=255, blank=True, default='/hotels')
    secondary_cta_text = models.CharField(max_length=60, blank=True, default='Contact Support')
    secondary_cta_link = models.CharField(max_length=255, blank=True, default='/dashboard/bookings')

    # --- Booking support -------------------------------------------------
    booking_support_enabled = models.BooleanField(default=True)
    booking_support_title = models.CharField(max_length=160, blank=True, default='Need help with a booking?')
    booking_support_description = models.TextField(blank=True)
    booking_support_button_text = models.CharField(max_length=60, blank=True, default='Manage my booking')
    booking_support_button_link = models.CharField(max_length=255, blank=True, default='/dashboard/bookings')

    # --- Guest support ---------------------------------------------------
    support_enabled = models.BooleanField(default=True)
    support_title = models.CharField(max_length=160, blank=True, default='Guest support')
    support_description = models.TextField(blank=True)

    # --- Contact cards / form / FAQ visibility ---------------------------
    cards_enabled = models.BooleanField(default=True, verbose_name='Show the contact cards')
    contact_form_enabled = models.BooleanField(default=True)
    faq_enabled = models.BooleanField(default=True)

    # --- Contact form ----------------------------------------------------
    form_success_message = models.CharField(
        max_length=255, blank=True, default='Thanks! Our team will get back to you shortly.'
    )
    form_error_message = models.CharField(
        max_length=255, blank=True, default='Something went wrong. Please try again.'
    )
    form_name_required = models.BooleanField(default=True)
    form_email_required = models.BooleanField(default=True)
    form_phone_enabled = models.BooleanField(default=True)
    form_phone_required = models.BooleanField(default=True)
    form_booking_reference_enabled = models.BooleanField(default=True)
    form_booking_reference_required = models.BooleanField(default=False)
    form_subject_required = models.BooleanField(default=True)
    form_message_required = models.BooleanField(default=True)

    # --- SEO -------------------------------------------------------------
    seo_title = models.CharField(max_length=160, blank=True, default='Contact SkyStay Hotels & Resorts')
    seo_description = models.TextField(
        blank=True,
        default='Contact SkyStay for hotel reservations, booking support, cancellations and guest assistance.',
    )

    class Meta:
        verbose_name = 'Contact page settings'
        verbose_name_plural = 'Contact page settings'

    def __str__(self):
        return self.page_title or 'Contact page settings'

    def clean(self):
        """Reject out-of-range coordinates and malformed phone numbers before saving."""
        errors = {}
        if self.latitude is not None and not -90 <= float(self.latitude) <= 90:
            errors['latitude'] = 'Latitude must be between -90 and 90.'
        if self.longitude is not None and not -180 <= float(self.longitude) <= 180:
            errors['longitude'] = 'Longitude must be between -180 and 180.'
        if self.phone and not PHONE_RE.match(self.phone.strip()):
            errors['phone'] = 'Enter a valid phone number, e.g. +91 98765 43210.'
        # Flag the half that is missing, so the admin fixes the right input.
        if self.latitude is None and self.longitude is not None:
            errors['latitude'] = 'Set both latitude and longitude so the map has a single point.'
        elif self.latitude is not None and self.longitude is None:
            errors['longitude'] = 'Set both latitude and longitude so the map has a single point.'
        if errors:
            raise ValidationError(errors)

    @property
    def linked_hotel(self):
        """The property this location mirrors, when one is linked."""
        return self.location_hotel

    @property
    def resolved_property_name(self):
        return (self.location_hotel.name if self.location_hotel else self.property_name) or ''

    @property
    def resolved_coordinates(self):
        """(latitude, longitude) as floats, or None when the map cannot be placed."""
        hotel = self.location_hotel
        if hotel and hotel.latitude is not None and hotel.longitude is not None:
            return float(hotel.latitude), float(hotel.longitude)
        if self.latitude is not None and self.longitude is not None:
            return float(self.latitude), float(self.longitude)
        return None

    @property
    def full_address(self):
        """Single line address for the location card and the footer."""
        hotel = self.location_hotel
        if hotel:
            parts = [hotel.address, hotel.city, hotel.country]
        else:
            parts = [self.address, self.city, self.state_region, self.country, self.postal_code]
        return ', '.join(part for part in parts if part)


class ContactCard(OrderedModel, TimeStampedModel):
    """A contact card (email / phone / location) shown on the Contact page.

    The card's *value* comes from ContactSettings — a card only controls its own
    presentation, so the admin never has to edit an address in two places.
    """

    class Kind(models.TextChoices):
        EMAIL = 'email', 'Email — uses the contact email'
        PHONE = 'phone', 'Phone — uses the contact phone'
        LOCATION = 'location', 'Location — uses the contact address & map'
        CUSTOM = 'custom', 'Custom link'

    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.EMAIL)
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    cta_label = models.CharField(max_length=60, blank=True, help_text='Text on the card link.')
    icon = models.CharField(
        max_length=60, blank=True,
        help_text='Icon keyword (mail, phone, map-pin, building, globe...). Defaults to the card type.',
    )
    cta_link = models.CharField(
        max_length=255, blank=True, help_text='Only used by a custom card, e.g. /hotels or https://...',
    )

    class Meta(OrderedModel.Meta):
        verbose_name = 'Contact card'
        verbose_name_plural = 'Contact cards'

    def __str__(self):
        return f'{self.get_kind_display()}: {self.title}'

    @property
    def resolved_icon(self):
        return self.icon or {
            self.Kind.EMAIL: 'mail',
            self.Kind.PHONE: 'phone',
            self.Kind.LOCATION: 'map-pin',
        }.get(self.kind, 'globe')


class ContactFaq(OrderedModel, TimeStampedModel):
    """A published FAQ entry; only ``is_active`` rows appear on the public page."""

    question = models.CharField(max_length=255)
    answer = models.TextField()

    class Meta(OrderedModel.Meta):
        verbose_name = 'Contact FAQ'
        verbose_name_plural = 'Contact FAQs'

    def __str__(self):
        return self.question


class ContactMessage(TimeStampedModel):
    """A submission from the public contact form, triaged in the admin."""

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        IN_PROGRESS = 'in_progress', 'In progress'
        RESOLVED = 'resolved', 'Resolved'
        ARCHIVED = 'archived', 'Archived'

    name = models.CharField(max_length=160)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    booking_reference = models.CharField(max_length=40, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Contact message'
        verbose_name_plural = 'Contact messages'

    def __str__(self):
        return f'{self.name} — {self.subject}'
