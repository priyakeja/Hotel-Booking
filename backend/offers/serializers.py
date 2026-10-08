"""Offer serializers.

The card/detail payloads are deliberately *structured* (numbers stay numbers,
discount type + value stay typed) so the frontend can render the right format —
“30% OFF”, “₹1,500 OFF”, “3 nights, 1 free” — without any hard-coded strings.
"""

from rest_framework import serializers

from content.models import SiteSettings
from core.serializers import ResolvedImageMixin
from core.utils import parse_date, room_availability_for_range
from hotels.models import Hotel, Room
from offers.models import Offer, OfferBenefit, OfferCategory, OfferImage, OfferSettings


def currency_symbol():
    try:
        return SiteSettings.load().currency_symbol or '₹'
    except Exception:  # pragma: no cover - during migrations
        return '₹'


class OfferCategorySerializer(serializers.ModelSerializer):
    offer_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = OfferCategory
        fields = ['id', 'name', 'slug', 'description', 'icon', 'order', 'offer_count']


class OfferBenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfferBenefit
        fields = ['id', 'text', 'icon', 'order']


class OfferImageSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = OfferImage
        fields = ['id', 'image', 'caption', 'alt_text', 'order']

    def get_image(self, obj):
        return self.resolved(obj.image, obj.image_url)


class OfferRoomSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    room_type_display = serializers.CharField(source='get_room_type_display', read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id', 'name', 'room_type', 'room_type_display', 'price_per_night',
            'capacity', 'max_guests', 'image',
        ]

    def get_image(self, obj):
        return self.resolved(obj.cover_image, obj.cover_image_url)


class OfferSettingsSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    hero_image = serializers.SerializerMethodField()

    class Meta:
        model = OfferSettings
        fields = [
            'page_title', 'page_description',
            'hero_enabled', 'hero_image', 'hero_search_enabled',
            'featured_enabled', 'featured_heading', 'featured_subheading',
            'limited_enabled', 'limited_heading', 'limited_subheading', 'limited_window_days',
            'seo_title', 'seo_description',
        ]

    def get_hero_image(self, obj):
        return self.resolved(obj.hero_image, obj.hero_image_url)


class OfferHotelSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    """Minimal hotel payload embedded into an offer card."""

    image = serializers.SerializerMethodField()
    location = serializers.CharField(read_only=True)
    rating = serializers.DecimalField(source='rating_average', max_digits=3, decimal_places=1, read_only=True)

    class Meta:
        model = Hotel
        fields = [
            'id', 'name', 'slug', 'city', 'country', 'location',
            'star_rating', 'image', 'rating', 'review_count',
        ]

    def get_image(self, obj):
        return self.resolved(obj.cover_image, obj.cover_image_url)


class OfferSerializerMixin:
    """Shared computed fields for the card and detail payloads."""

    def _range(self):
        request = self.context.get('request')
        if not request:
            return None, None
        return (
            parse_date(request.query_params.get('check_in')),
            parse_date(request.query_params.get('check_out')),
        )

    def _discount(self, obj):
        return {
            'discount_type': obj.discount_type,
            'discount_type_display': obj.get_discount_type_display(),
            'discount_value': f'{obj.discount_value:.2f}',
            'discount_percent': obj.discount_percent,
            'free_nights': obj.free_nights,
            'original_price': f'{obj.base_price:.2f}',
            'offer_price': f'{obj.offer_price:.2f}',
            'saving': f'{obj.saving:.2f}',
            'currency_symbol': currency_symbol(),
        }


class OfferCardSerializer(OfferSerializerMixin, ResolvedImageMixin, serializers.ModelSerializer):
    category = OfferCategorySerializer(read_only=True)
    hotel = OfferHotelSerializer(read_only=True)
    benefits = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    offer_type_display = serializers.CharField(source='get_offer_type_display', read_only=True)
    status = serializers.CharField(source='compute_status', read_only=True)
    status_label = serializers.CharField(read_only=True)
    is_available = serializers.SerializerMethodField()
    rooms_left = serializers.SerializerMethodField()
    room_names = serializers.SerializerMethodField()
    room_type_labels = serializers.SerializerMethodField()
    ends_soon = serializers.SerializerMethodField()
    valid_from = serializers.DateField(source='start_date', read_only=True)
    valid_until = serializers.DateField(source='end_date', read_only=True)
    days_until_end = serializers.IntegerField(read_only=True)

    class Meta:
        model = Offer
        fields = [
            'id', 'slug', 'title', 'short_description',
            'offer_type', 'offer_type_display', 'category',
            'hotel', 'image', 'status', 'status_label', 'is_featured',
            'room_names', 'room_type_labels',
            'valid_from', 'valid_until', 'days_until_end', 'ends_soon',
            'promo_code_enabled', 'promo_code',
            'benefits', 'is_available', 'rooms_left',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.update(self._discount(instance))
        return data

    def get_image(self, obj):
        return self.resolved(obj.image, obj.image_url)

    def get_benefits(self, obj):
        return OfferBenefitSerializer(
            [b for b in obj.benefits.all() if b.is_active], many=True
        ).data

    def get_room_names(self, obj):
        return [room.name for room in obj.applicable_rooms()]

    def get_room_type_labels(self, obj):
        labels = []
        for room in obj.applicable_rooms():
            label = room.get_room_type_display()
            if label not in labels:
                labels.append(label)
        return labels

    def get_ends_soon(self, obj):
        window = OfferSettings.load().limited_window_days or 7
        return obj.ends_within(window)

    def get_is_available(self, obj):
        check_in, check_out = self._range()
        if not check_in or not check_out:
            return True
        for room in obj.applicable_rooms():
            available, _ = room_availability_for_range(room, check_in, check_out)
            if available:
                return True
        return False

    def get_rooms_left(self, obj):
        check_in, check_out = self._range()
        rooms = obj.applicable_rooms()
        if not check_in or not check_out:
            return sum(room.total_rooms for room in rooms)
        return sum(room_availability_for_range(room, check_in, check_out)[1] for room in rooms)


class OfferDetailSerializer(OfferCardSerializer):
    images = OfferImageSerializer(many=True, read_only=True)
    rooms = serializers.SerializerMethodField()
    terms = serializers.SerializerMethodField()

    class Meta(OfferCardSerializer.Meta):
        fields = OfferCardSerializer.Meta.fields + [
            'description', 'images', 'rooms', 'terms',
            'min_stay', 'max_stay', 'min_booking_amount',
            'blackout_start', 'blackout_end', 'display_order',
            'view_count', 'click_count', 'booking_count',
            'created_at', 'updated_at',
        ]

    def get_rooms(self, obj):
        return OfferRoomSerializer(obj.applicable_rooms(), many=True, context=self.context).data

    def get_terms(self, obj):
        return obj.terms_list()
