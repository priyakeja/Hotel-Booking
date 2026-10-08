from datetime import date
from decimal import Decimal

from django.db.models import F
from django.utils import timezone
from rest_framework import serializers

from bookings.models import Booking
from core.serializers import ResolvedImageMixin
from core.utils import nights_between, room_availability_for_range
from hotels.models import Room
from offers.models import Offer


class BookingRoomSummarySerializer(ResolvedImageMixin, serializers.Serializer):
    """Minimal room + hotel info embedded into booking responses."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    room_type = serializers.CharField()
    bed_type = serializers.CharField()
    capacity = serializers.IntegerField()
    price_per_night = serializers.DecimalField(max_digits=10, decimal_places=2)
    hotel_name = serializers.CharField(source='hotel.name')
    hotel_slug = serializers.CharField(source='hotel.slug')
    hotel_city = serializers.CharField(source='hotel.city')
    hotel_country = serializers.CharField(source='hotel.country')
    # Read-only imagery so the dashboard can show a real photo (uploaded file
    # preferred, external CMS URL as fallback) instead of a placeholder icon.
    hotel_image = serializers.SerializerMethodField()
    room_image = serializers.SerializerMethodField()

    def get_hotel_image(self, obj):
        hotel = obj.hotel
        return (
            self.resolved(hotel.cover_image, hotel.cover_image_url)
            or self.get_room_image(obj)
        )

    def get_room_image(self, obj):
        return self.resolved(obj.cover_image, obj.cover_image_url)


class BookingSerializer(serializers.ModelSerializer):
    room_detail = BookingRoomSummarySerializer(source='room', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)
    nights = serializers.IntegerField(read_only=True)
    payment_method = serializers.ChoiceField(
        choices=[('razorpay', 'Razorpay'), ('cash', 'Cash')],
        default='razorpay',
        write_only=True,
        required=False,
    )
    payment_provider = serializers.SerializerMethodField(read_only=True)
    cash_received = serializers.SerializerMethodField(read_only=True)
    cash_remaining = serializers.SerializerMethodField(read_only=True)
    offer_slug = serializers.CharField(source='offer.slug', read_only=True, default=None)
    offer_title = serializers.CharField(source='offer.title', read_only=True, default=None)

    # Replaced with a filtered queryset in __init__; the declaration here just keeps
    # the relation writable so clients post a room id.
    room = serializers.PrimaryKeyRelatedField(queryset=Room.objects.none(), write_only=True)
    #: Optional promotion applied to the stay. Accepts the offer slug; the price
    #: and eligibility are resolved on the server in ``validate``.
    offer = serializers.SlugRelatedField(
        slug_field='slug', queryset=Offer.objects.none(), write_only=True,
        required=False, allow_null=True,
    )
    # All three default to the signed-in customer's profile when omitted.
    guest_name = serializers.CharField(required=False, allow_blank=True)
    guest_email = serializers.EmailField(required=False, allow_blank=True)
    guest_phone = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'reference', 'room', 'room_detail', 'check_in', 'check_out',
            'nights', 'guests', 'rooms_count', 'price_per_night', 'subtotal',
            'tax_amount', 'total_price', 'status', 'status_display',
            'payment_status', 'payment_status_display', 'payment_method',
            'payment_provider', 'cash_received', 'cash_remaining',
            'offer', 'offer_slug', 'offer_title',
            'special_requests', 'guest_name', 'guest_email', 'guest_phone',
            'can_be_cancelled', 'created_at',
        ]
        read_only_fields = [
            'id', 'reference', 'status', 'payment_status', 'price_per_night', 'subtotal',
            'tax_amount', 'total_price', 'created_at', 'nights',
        ]

    def get_payment_provider(self, obj):
        payment = getattr(obj, 'payment', None)
        return payment.provider if payment else 'razorpay'

    def get_cash_received(self, obj):
        payment = getattr(obj, 'payment', None)
        return f'{payment.cash_received:.2f}' if payment else '0.00'

    def get_cash_remaining(self, obj):
        payment = getattr(obj, 'payment', None)
        return f'{payment.cash_remaining:.2f}' if payment else f'{obj.total_price:.2f}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['room'].queryset = Room.objects.filter(is_active=True, hotel__is_active=True)
        self.fields['offer'].queryset = Offer.objects.filter(is_published=True, is_disabled=False)

    # -- validation ------------------------------------------------------
    def validate(self, attrs):
        room = attrs.get('room') or getattr(self.instance, 'room', None)
        check_in = attrs.get('check_in') or getattr(self.instance, 'check_in', None)
        check_out = attrs.get('check_out') or getattr(self.instance, 'check_out', None)
        guests = attrs.get('guests', getattr(self.instance, 'guests', 1))
        rooms_count = attrs.get('rooms_count', getattr(self.instance, 'rooms_count', 1))

        if not room or not check_in or not check_out:
            raise serializers.ValidationError('Room, check-in and check-out are required.')

        if check_in < timezone.localdate():
            raise serializers.ValidationError({'check_in': 'Check-in cannot be in the past.'})

        if check_out <= check_in:
            raise serializers.ValidationError({'check_out': 'Check-out must be after check-in.'})

        if nights_between(check_in, check_out) > 30:
            raise serializers.ValidationError({'check_out': 'Stays are limited to 30 nights.'})

        if guests > room.max_guests * rooms_count:
            raise serializers.ValidationError(
                {'guests': f'{room.name} allows up to {room.max_guests} guests per room.'}
            )

        available, rooms_left = room_availability_for_range(
            room, check_in, check_out, exclude_booking=self.instance
        )
        if not available or rooms_left < rooms_count:
            raise serializers.ValidationError(
                {'room': f'Sorry, only {rooms_left} room(s) of this type are left for those dates.'}
            )

        attrs['room'] = room
        self._validate_offer(attrs, room, check_in, check_out, rooms_count)
        return attrs

    def _validate_offer(self, attrs, room, check_in, check_out, rooms_count):
        """Validate the promotion server-side — never trust a client-sent price."""
        offer = attrs.get('offer')
        if not offer:
            return

        problems = []
        if not offer.is_live:
            problems.append('This offer is no longer available.')
        if room.hotel_id != offer.hotel_id:
            problems.append('This offer is not valid for the selected hotel.')
        elif not offer.room_is_eligible(room):
            problems.append('This offer is not valid for the selected room.')
        problems.extend(offer.validate_stay(check_in, check_out))

        if offer.min_booking_amount:
            subtotal = offer.nightly_price_for(room) * nights_between(check_in, check_out) * rooms_count
            if subtotal < Decimal(offer.min_booking_amount):
                problems.append(
                    f'This offer requires a minimum booking amount of {offer.min_booking_amount}. '
                    f'Please add more nights or rooms.'
                )

        if problems:
            raise serializers.ValidationError({'offer': problems})

    def create(self, validated_data):
        from django.db import transaction

        payment_method = validated_data.pop('payment_method', 'razorpay')
        offer = validated_data.pop('offer', None)
        request = self.context['request']
        user = request.user
        room = validated_data['room']
        check_in = validated_data['check_in']
        check_out = validated_data['check_out']
        rooms_count = validated_data.get('rooms_count', 1)
        guests = validated_data.get('guests', 1)

        with transaction.atomic():
            # Acquire database lock on the room row to protect availability check & booking creation against race conditions
            locked_room = Room.objects.select_for_update().get(pk=room.pk)

            available, rooms_left = room_availability_for_range(
                locked_room, check_in, check_out, exclude_booking=self.instance
            )
            if not available or rooms_left < rooms_count:
                raise serializers.ValidationError(
                    {'room': f'Sorry, only {rooms_left} room(s) of this type are left for those dates.'}
                )

            is_cash = payment_method == 'cash'
            # The offer price is recomputed here from the live room rate; a stale
            # client-side price can never leak into the booking.
            nightly = offer.nightly_price_for(locked_room) if offer else locked_room.price_per_night
            booking = Booking.objects.create(
                user=user,
                room=locked_room,
                offer=offer,
                check_in=check_in,
                check_out=check_out,
                guests=guests,
                rooms_count=rooms_count,
                special_requests=validated_data.get('special_requests', ''),
                guest_name=validated_data.get('guest_name') or user.display_name,
                guest_email=validated_data.get('guest_email') or user.email,
                guest_phone=validated_data.get('guest_phone') or user.phone,
                price_per_night=nightly,
                status=Booking.Status.CONFIRMED if is_cash else Booking.Status.PENDING,
                payment_status=Booking.PaymentStatus.UNPAID,
            )
            if offer:
                Offer.objects.filter(pk=offer.pk).update(booking_count=F('booking_count') + 1)

            if is_cash:
                from bookings.models import Payment

                Payment.objects.create(
                    booking=booking,
                    provider='cash',
                    order_id=f'CASH-{booking.reference}',
                    amount=booking.total_price,
                    cash_received=Decimal('0'),
                    status=Payment.Status.CREATED,
                )

        return booking


class AvailabilityQuerySerializer(serializers.Serializer):
    check_in = serializers.DateField()
    check_out = serializers.DateField()
    guests = serializers.IntegerField(required=False, min_value=1, default=1)

    def validate(self, attrs):
        if attrs['check_out'] <= attrs['check_in']:
            raise serializers.ValidationError({'check_out': 'Check-out must be after check-in.'})
        if attrs['check_in'] < date.today():
            raise serializers.ValidationError({'check_in': 'Check-in cannot be in the past.'})
        return attrs
