from rest_framework import serializers

from content.serializers import AmenitySerializer
from core.serializers import ResolvedImageMixin
from core.utils import room_availability_for_range
from hotels.models import Hotel, HotelImage, NearbyFacility, Room, RoomImage


class NearbyFacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = NearbyFacility
        fields = ['id', 'name', 'category', 'description', 'distance_km', 'icon', 'order']


class ImageSerializer(ResolvedImageMixin, serializers.ModelSerializer):

    image = serializers.SerializerMethodField()

    class Meta:
        fields = ['id', 'image', 'caption', 'alt_text', 'order']

    def get_image(self, obj):
        return self.resolved(obj.image, obj.image_url)


class HotelImageSerializer(ImageSerializer):
    class Meta(ImageSerializer.Meta):
        model = HotelImage


class RoomImageSerializer(ImageSerializer):
    class Meta(ImageSerializer.Meta):
        model = RoomImage


class RoomSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    room_type_display = serializers.CharField(source='get_room_type_display', read_only=True)
    image = serializers.SerializerMethodField()
    images = RoomImageSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(source='amenity_list', many=True, read_only=True)
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    hotel_slug = serializers.CharField(source='hotel.slug', read_only=True)
    rooms_left = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    price_with_tax = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'id', 'hotel', 'hotel_name', 'hotel_slug', 'name', 'room_type',
            'room_type_display', 'description', 'price_per_night', 'price_with_tax',
            'capacity', 'max_guests', 'bed_type', 'beds', 'size_sqm',
            'total_rooms', 'rooms_left', 'is_available', 'is_active',
            'image', 'images', 'amenities', 'order',
        ]
        read_only_fields = ['hotel']

    # -- helpers ---------------------------------------------------------
    def get_image(self, obj):
        return self.resolved(obj.cover_image, obj.cover_image_url)

    def _requested_range(self):
        request = self.context.get('request')
        if not request:
            return None, None
        from core.utils import parse_date

        return (
            parse_date(request.query_params.get('check_in')),
            parse_date(request.query_params.get('check_out')),
        )

    def get_rooms_left(self, obj):
        check_in, check_out = self._requested_range()
        if not check_in or not check_out:
            return obj.total_rooms
        _, left = room_availability_for_range(obj, check_in, check_out)
        return left

    def get_is_available(self, obj):
        check_in, check_out = self._requested_range()
        if not check_in or not check_out:
            return obj.total_rooms > 0
        available, _ = room_availability_for_range(obj, check_in, check_out)
        return available

    def get_price_with_tax(self, obj):
        site = self.context.get('site_settings')
        try:
            from content.models import SiteSettings

            site = site or SiteSettings.load()
            rate = site.tax_percentage or 0
        except Exception:  # pragma: no cover
            rate = 0
        from decimal import Decimal

        multiplier = Decimal('1') + (Decimal(rate) / Decimal('100'))
        return str((obj.price_per_night * multiplier).quantize(Decimal('0.01')))


class HotelListSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    """Compact payload for cards on the listing/home pages."""

    image = serializers.SerializerMethodField()
    location = serializers.CharField(read_only=True)
    rating = serializers.DecimalField(source='rating_average', max_digits=3, decimal_places=1, read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    starting_price = serializers.DecimalField(source='price_per_night', max_digits=10, decimal_places=2, read_only=True)
    room_count = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Hotel
        fields = [
            'id', 'name', 'slug', 'city', 'state', 'country', 'location', 'short_description',
            'star_rating', 'price_per_night', 'starting_price', 'image', 'is_featured',
            'rating', 'review_count', 'room_count', 'is_available',
        ]

    def get_image(self, obj):
        return self.resolved(obj.cover_image, obj.cover_image_url)

    def get_room_count(self, obj):
        # Prefer the annotated value from the queryset to avoid an extra query per card.
        annotated = getattr(obj, 'room_count_annotated', None)
        return annotated if annotated is not None else obj.active_rooms.count()

    def get_is_available(self, obj):
        """True when at least one room type still has inventory for the dates."""
        request = self.context.get('request')
        if not request:
            return True
        from core.utils import parse_date

        check_in = parse_date(request.query_params.get('check_in'))
        check_out = parse_date(request.query_params.get('check_out'))
        if not check_in or not check_out:
            return True
        for room in obj.active_rooms.all():
            available, _ = room_availability_for_range(room, check_in, check_out)
            if available:
                return True
        return False


class HotelDetailSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    images = HotelImageSerializer(many=True, read_only=True)
    amenities = AmenitySerializer(many=True, read_only=True)
    nearby_facilities = NearbyFacilitySerializer(many=True, read_only=True)
    highlights = serializers.ListField(source='highlight_list', read_only=True)
    rooms = serializers.SerializerMethodField()
    rating = serializers.DecimalField(source='rating_average', max_digits=3, decimal_places=1, read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    location = serializers.CharField(read_only=True)
    room_type_summary = serializers.SerializerMethodField()

    class Meta:
        model = Hotel
        fields = [
            'id', 'name', 'slug', 'city', 'state', 'country', 'address', 'location',
            'short_description', 'description', 'star_rating', 'price_per_night',
            'image', 'images', 'amenities', 'nearby_facilities', 'highlights', 'latitude', 'longitude',
            'is_featured', 'rooms', 'rating', 'review_count', 'room_type_summary',
        ]


    def get_image(self, obj):
        return self.resolved(obj.cover_image, obj.cover_image_url)

    def get_rooms(self, obj):
        rooms = obj.rooms.filter(is_active=True)
        return RoomSerializer(rooms, many=True, context=self.context).data

    def get_room_type_summary(self, obj):
        types = (
            obj.rooms.filter(is_active=True)
            .values_list('room_type', flat=True)
            .distinct()
        )
        return list(types)
