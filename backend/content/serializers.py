import re

from django.utils.html import strip_tags
from rest_framework import serializers

from content.models import (
    Amenity,
    ContactCard,
    ContactFaq,
    ContactMessage,
    ContactSettings,
    Feature,
    GalleryImage,
    HeroBanner,
    NavLink,
    SiteSettings,
    Testimonial,
    TextSection,
)
from core.serializers import ResolvedImageMixin


class NavLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = NavLink
        fields = ['id', 'label', 'url', 'location', 'open_in_new_tab', 'order', 'is_active']


class SiteSettingsSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    logo_display = serializers.SerializerMethodField()
    favicon_display = serializers.SerializerMethodField()
    header_links = serializers.SerializerMethodField()
    footer_links = serializers.SerializerMethodField()
    legal_links = serializers.SerializerMethodField()

    class Meta:
        model = SiteSettings
        fields = [
            'site_title', 'tagline', 'logo_display', 'favicon_display', 'footer_text',
            'meta_description', 'contact_email', 'contact_phone', 'address',
            'facebook_url', 'instagram_url', 'twitter_url', 'youtube_url',
            'currency_code', 'currency_symbol', 'default_check_in_time',
            'default_check_out_time', 'tax_percentage',
            'header_links', 'footer_links', 'legal_links',
        ]

    def _links(self, obj, location):
        # Nav links are global (not per-settings-row), so query the model directly.
        queryset = NavLink.objects.filter(location=location, is_active=True)
        return NavLinkSerializer(queryset, many=True).data

    def get_logo_display(self, obj):
        return self.resolved(obj.logo, obj.logo_url)

    def get_favicon_display(self, obj):
        return self.resolved(obj.favicon, '')

    def get_header_links(self, obj):
        return self._links(obj, NavLink.Location.HEADER)

    def get_footer_links(self, obj):
        return self._links(obj, NavLink.Location.FOOTER)

    def get_legal_links(self, obj):
        return self._links(obj, NavLink.Location.FOOTER_LEGAL)


class ContactSettingsSerializer(serializers.ModelSerializer):
    """The Contact page settings, with the location already resolved.

    When a property is linked, its name/address/coordinates replace the manual
    values, so the frontend never has to know whether a hotel is attached.
    """

    location = serializers.SerializerMethodField()

    class Meta:
        model = ContactSettings
        fields = [
            'page_title', 'intro_message', 'response_time', 'intro_enabled',
            'email', 'phone', 'support_hours',
            'location', 'map_enabled',
            'primary_cta_text', 'primary_cta_link', 'secondary_cta_text', 'secondary_cta_link',
            'booking_support_enabled', 'booking_support_title', 'booking_support_description',
            'booking_support_button_text', 'booking_support_button_link',
            'support_enabled', 'support_title', 'support_description',
            'cards_enabled', 'contact_form_enabled', 'faq_enabled',
            'form_success_message', 'form_error_message',
            'form_name_required', 'form_email_required',
            'form_phone_enabled', 'form_phone_required',
            'form_booking_reference_enabled', 'form_booking_reference_required',
            'form_subject_required', 'form_message_required',
            'seo_title', 'seo_description',
        ]

    def get_location(self, obj):
        hotel = obj.location_hotel
        coordinates = obj.resolved_coordinates
        if hotel:
            parts = {
                'property_name': hotel.name,
                'address': hotel.address,
                'city': hotel.city,
                'state_region': '',
                'country': hotel.country,
                'postal_code': '',
            }
        else:
            parts = {
                'property_name': obj.property_name,
                'address': obj.address,
                'city': obj.city,
                'state_region': obj.state_region,
                'country': obj.country,
                'postal_code': obj.postal_code,
            }
        return {
            **parts,
            'full_address': obj.full_address,
            'latitude': coordinates[0] if coordinates else None,
            'longitude': coordinates[1] if coordinates else None,
            'has_coordinates': coordinates is not None,
        }


class ContactCardSerializer(serializers.ModelSerializer):
    icon = serializers.CharField(source='resolved_icon', read_only=True)

    class Meta:
        model = ContactCard
        fields = ['id', 'kind', 'title', 'description', 'cta_label', 'icon', 'cta_link', 'order']


class ContactFaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactFaq
        fields = ['id', 'question', 'answer', 'order']


class ContactMessageSerializer(serializers.ModelSerializer):
    """Write serializer for the public contact form.

    Field requirements are driven by the admin's Contact form settings, and the
    submitted text is stripped of HTML before it is stored.
    """

    #: Shortest accepted name; guards against one-letter submissions.
    NAME_MIN = 3

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'booking_reference', 'subject', 'message']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = ContactSettings.load()
        required = {
            'name': config.form_name_required,
            'email': config.form_email_required,
            'subject': config.form_subject_required,
            'message': config.form_message_required,
        }
        for field, is_required in required.items():
            self.fields[field].required = is_required
            self.fields[field].allow_blank = not is_required
            self.fields[field].allow_null = False

        if not config.form_phone_enabled:
            self.fields.pop('phone', None)
        else:
            self.fields['phone'].required = config.form_phone_required
            self.fields['phone'].allow_blank = not config.form_phone_required

        if not config.form_booking_reference_enabled:
            self.fields.pop('booking_reference', None)
        else:
            self.fields['booking_reference'].required = config.form_booking_reference_required
            self.fields['booking_reference'].allow_blank = not config.form_booking_reference_required

    def _clean(self, value):
        return strip_tags(value or '').strip()

    def validate_name(self, value):
        cleaned = self._clean(value)
        if cleaned and len(cleaned) < self.NAME_MIN:
            raise serializers.ValidationError(
                f'Name must be at least {self.NAME_MIN} characters.'
            )
        return cleaned

    def validate_phone(self, value):
        """Accept a 10-digit mobile, with or without a pasted +91 / 0 prefix."""
        if not value:
            return ''
        digits = re.sub(r'\D', '', value)
        if len(digits) == 12 and digits.startswith('91'):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith('0'):
            digits = digits[1:]
        if not re.match(r'^\d{10}$', digits):
            raise serializers.ValidationError(
                'Enter a valid 10-digit mobile number.'
            )
        return digits

    def validate_subject(self, value):
        return self._clean(value)

    def validate_message(self, value):
        return self._clean(value)

    def validate_booking_reference(self, value):
        cleaned = self._clean(value).upper()
        if cleaned and not all(char.isalnum() or char in '-_/' for char in cleaned):
            raise serializers.ValidationError('Enter a valid booking reference, e.g. SKY-7F3K9A.')
        return cleaned


class HeroBannerSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = HeroBanner
        fields = [
            'id', 'eyebrow', 'title', 'subtitle', 'description', 'image',
            'overlay_opacity', 'cta_text', 'cta_link', 'secondary_cta_text',
            'secondary_cta_link', 'show_search_form', 'order',
        ]

    def get_image(self, obj):
        return self.resolved(obj.background, obj.background_url)


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'icon', 'title', 'description', 'order']


class AmenitySerializer(serializers.ModelSerializer):
    hotel_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Amenity
        fields = ['id', 'name', 'icon', 'description', 'order', 'show_on_homepage', 'hotel_count']


class TestimonialSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    hotel_name = serializers.CharField(source='hotel.name', read_only=True, default=None)

    class Meta:
        model = Testimonial
        fields = ['id', 'name', 'location', 'message', 'rating', 'image', 'hotel_name', 'order']

    def get_image(self, obj):
        return self.resolved(obj.avatar, obj.avatar_url)


class GalleryImageSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = GalleryImage
        fields = ['id', 'title', 'caption', 'alt_text', 'image', 'order']

    def get_image(self, obj):
        return self.resolved(obj.image, obj.image_url)


class TextSectionSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    gallery = GalleryImageSerializer(many=True, read_only=True)

    class Meta:
        model = TextSection
        fields = [
            'id', 'key', 'eyebrow', 'heading', 'subheading', 'body', 'image',
            'cta_text', 'cta_link', 'gallery', 'order',
        ]

    def get_image(self, obj):
        return self.resolved(obj.image, obj.image_url)
