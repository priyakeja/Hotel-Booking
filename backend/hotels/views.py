import logging
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Max, Min, Q, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from content.models import Amenity, SiteSettings, TextSection
from content.serializers import AmenitySerializer, TextSectionSerializer
from core.search import normalize_text, hotel_matches_search
from core.utils import money, nights_between, parse_date, room_availability_for_range
from hotels.models import Hotel, Room
from hotels.serializers import HotelDetailSerializer, HotelListSerializer, RoomSerializer

logger = logging.getLogger(__name__)

ORDERING_MAP = {
    'popular': ('-is_featured', '-rating_average', 'name'),
    'price_low': ('price_per_night', 'name'),
    'price_high': ('-price_per_night', 'name'),
    'rating': ('-rating_average', 'name'),
    'newest': ('-created_at',),
    'name': ('name',),
}

#: Query values that switch a boolean filter on.
TRUE_VALUES = ('1', 'true', 'yes', 'on')

#: Fields loaded to run the tolerant free-text search in Python.
SEARCH_FIELDS = ('id', 'name', 'city', 'state', 'country', 'address', 'short_description', 'description')


def _truthy(value):
    return str(value or '').strip().lower() in TRUE_VALUES


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class HotelViewSet(viewsets.ReadOnlyModelViewSet):
    """Public hotel catalogue. Filtering is driven entirely by query params.

    The pipeline is applied in a fixed order so a filter the visitor never asked
    for can never silently empty the results::

        active hotels → destination search → intentional featured
        → date availability → guest/room capacity → price → star → room type
        → amenities → sorting

    Date availability and capacity are applied when the listing is rendered
    (``list``), not in ``get_queryset``, so a sold-out hotel's detail page still
    resolves.
    """

    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_serializer_class(self):
        return HotelDetailSerializer if self.action == 'retrieve' else HotelListSerializer

    # -- base queryset ----------------------------------------------------
    def _base_queryset(self):
        """Every active hotel, with the joins/annotations the listing needs."""
        return (
            Hotel.objects.filter(is_active=True)
            .prefetch_related('images', 'rooms__images', 'rooms__amenity_list', 'nearby_facilities')
            .annotate(
                room_count_annotated=Count('rooms', filter=Q(rooms__is_active=True), distinct=True)
            )
        )

    def get_queryset(self):
        queryset = self._apply_location(self._base_queryset())
        queryset = self._apply_intent_filters(queryset)
        order_key = self.request.query_params.get('sort') or self.request.query_params.get('ordering') or 'popular'
        return queryset.order_by(*ORDERING_MAP.get(order_key, ORDERING_MAP['popular']))

    # -- pipeline stages --------------------------------------------------
    def _apply_location(self, queryset):
        """Normalised destination search across city/state/country/name/address."""
        params = self.request.query_params

        search = params.get('search')
        if search and search.strip():
            queryset = self._search(queryset, search)

        city = params.get('city')
        if city and city.lower() != 'all':
            cities = [normalize_text(value) for value in city.split(',') if value.strip()]
            if cities:
                condition = Q()
                for value in cities:
                    condition |= Q(city__iexact=value)
                queryset = queryset.filter(condition)

        return queryset

    def _search(self, queryset, search):
        """Tolerant free-text filter — never an exact-string requirement."""
        rows = queryset.values(*SEARCH_FIELDS)
        ids = [row['id'] for row in rows if hotel_matches_search(row, search)]
        if not ids:
            return queryset.none()
        return queryset.filter(id__in=ids)

    def _apply_intent_filters(self, queryset):
        """Filters the visitor explicitly asked for. Featured is opt-in only."""
        params = self.request.query_params

        # Featured is applied *only* when the request explicitly says so (the
        # Featured Hotels experience / an explicit toggle). A normal search must
        # never inherit it.
        if _truthy(params.get('featured')):
            queryset = queryset.filter(is_featured=True)

        min_price = params.get('min_price')
        if min_price:
            try:
                queryset = queryset.filter(price_per_night__gte=Decimal(min_price))
            except (TypeError, ValueError):
                pass

        max_price = params.get('max_price')
        if max_price:
            try:
                queryset = queryset.filter(price_per_night__lte=Decimal(max_price))
            except (TypeError, ValueError):
                pass

        star_ratings = [s for s in (params.getlist('star_rating') if hasattr(params, 'getlist') else []) if s]
        if not star_ratings and params.get('star_rating'):
            star_ratings = [params.get('star_rating')]
        floors = []
        for star in star_ratings:
            try:
                floors.append(int(float(star)))
            except (TypeError, ValueError):
                continue
        if floors:
            condition = Q()
            for floor in floors:
                condition |= Q(star_rating__gte=floor) & Q(star_rating__lt=floor + 1)
            queryset = queryset.filter(condition)

        amenity_names = [a for a in (params.getlist('amenity') if hasattr(params, 'getlist') else []) if a]
        if not amenity_names and params.get('amenity'):
            amenity_names = [params.get('amenity')]
        if amenity_names:
            for name in amenity_names:
                queryset = queryset.filter(amenities__name__iexact=name)
            queryset = queryset.distinct()

        room_type = params.get('room_type')
        if room_type and room_type.lower() != 'all':
            queryset = queryset.filter(rooms__room_type=room_type, rooms__is_active=True).distinct()

        return queryset

    # -- availability & capacity (listing only) ---------------------------
    def _apply_availability(self, queryset, check_in, check_out, guests, rooms, has_dates):
        """Keep only hotels with real inventory for the dates / party size."""
        if not has_dates:
            # Without dates we can still respect a capacity request, using the
            # admin-managed room configuration rather than a hard-coded number.
            if guests:
                room_ids = Room.objects.filter(is_active=True, max_guests__gte=guests).values('hotel_id')
                queryset = queryset.filter(id__in=room_ids)
            elif rooms:
                room_ids = Room.objects.filter(is_active=True, total_rooms__gte=rooms).values('hotel_id')
                queryset = queryset.filter(id__in=room_ids)
            return queryset

        hotel_ids = list(queryset.values_list('id', flat=True))
        available_ids = self._available_hotel_ids(hotel_ids, check_in, check_out, guests, rooms)
        if not available_ids:
            return queryset.none()
        return queryset.filter(id__in=available_ids)

    def _available_hotel_ids(self, hotel_ids, check_in, check_out, guests, rooms):
        """Hotel ids with at least one room type that fits the party and dates."""
        from bookings.models import Booking

        if not hotel_ids:
            return set()

        room_list = list(Room.objects.filter(is_active=True, hotel_id__in=hotel_ids))
        if not room_list:
            return set()

        room_ids = [room.id for room in room_list]
        # One query for all overlapping reservations, instead of one per room.
        booked = {
            row['room_id']: row['total'] or 0
            for row in Booking.objects.filter(
                status__in=Booking.BLOCKING_STATUSES,
                check_in__lt=check_out,
                check_out__gt=check_in,
                room_id__in=room_ids,
            )
            .values('room_id')
            .annotate(total=Sum('rooms_count'))
        }

        available = set()
        for room in room_list:
            left = max((room.total_rooms or 0) - booked.get(room.id, 0), 0)
            if left <= 0:
                continue

            capacity = max(room.max_guests or 1, 1)
            if guests:
                if rooms:
                    # Explicit room count: capacity must cover the party in those rooms.
                    if capacity * rooms < guests:
                        continue
                    required = rooms
                else:
                    # Derive how many of this room type the party needs.
                    required = -(-guests // capacity)
                if required > left:
                    continue
            elif rooms and rooms > left:
                continue

            available.add(room.hotel_id)

        return available

    # -- listing ----------------------------------------------------------
    def list(self, request, *args, **kwargs):
        params = request.query_params
        check_in = parse_date(params.get('check_in'))
        check_out = parse_date(params.get('check_out'))
        has_dates = bool(check_in and check_out and check_out > check_in)
        guests = _as_int(params.get('guests'))
        rooms = _as_int(params.get('rooms'))

        queryset = self.filter_queryset(self.get_queryset())
        pre_availability = queryset
        queryset = self._apply_availability(queryset, check_in, check_out, guests, rooms, has_dates)

        self._log_stages(pre_availability, queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
        else:
            serializer = self.get_serializer(queryset, many=True)
            response = Response(serializer.data)

        if isinstance(response.data, dict) and response.data.get('count', 0) == 0:
            response.data['meta'] = self._empty_meta(
                pre_availability, check_in, check_out, guests, rooms, has_dates
            )
        return response

    # -- diagnostics ------------------------------------------------------
    def _log_stages(self, pre_availability, final):
        """Explain which stage emptied the results (opt-in via ``?debug=1``)."""
        if not (settings.DEBUG and _truthy(self.request.query_params.get('debug'))):
            return
        base = self._base_queryset().count()
        located = self._apply_location(self._base_queryset()).count()
        logger.info(
            '[hotel-search] params=%s | active=%s | after location=%s | '
            'after filters=%s | final=%s',
            self.request.query_params.urlencode(),
            base,
            located,
            pre_availability.count(),
            final.count(),
        )

    def _empty_meta(self, pre_availability, check_in, check_out, guests, rooms, has_dates):
        """Why did the search return nothing? Drives the helpful empty states."""
        params = self.request.query_params
        base = self._base_queryset()
        location_matched = self._apply_location(base).count()

        meta = {
            'empty_reason': 'filters',
            'total_hotels': base.count(),
            'location_matched': location_matched,
            'before_availability': pre_availability.count(),
        }

        if location_matched == 0 and (params.get('search') or params.get('city')):
            meta['empty_reason'] = 'location'
            return meta

        if has_dates and meta['before_availability'] > 0:
            # Availability ignoring the party size tells capacity apart from
            # "nothing free for these dates".
            available_without_capacity = self._apply_availability(
                pre_availability, check_in, check_out, None, None, has_dates
            ).count()
            meta['availability_matched'] = available_without_capacity
            if available_without_capacity == 0:
                meta['empty_reason'] = 'availability'
            elif guests or rooms:
                meta['empty_reason'] = 'capacity'
            else:
                meta['empty_reason'] = 'filters'
            return meta

        return meta

    # -- extra endpoints --------------------------------------------------
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def filters(self, request):
        """Metadata used to build the listing page filter sidebar."""
        cities = (
            Hotel.objects.filter(is_active=True)
            .values('city', 'country')
            .annotate(total=Count('id'))
            .order_by('city')
        )
        price_bounds = Hotel.objects.filter(is_active=True).aggregate(
            min=Min('price_per_night'), max=Max('price_per_night')
        )
        section = TextSection.objects.filter(key=TextSection.Key.HOTELS_LISTING, is_active=True).first()
        return Response(
            {
                'locations': [
                    {
                        'city': row['city'],
                        'country': row['country'],
                        'label': f"{row['city']}, {row['country']}",
                        'hotels': row['total'],
                    }
                    for row in cities
                ],
                'price_range': {
                    'min': money(price_bounds['min']),
                    'max': money(price_bounds['max'] or Decimal('500')),
                },
                'star_ratings': [5, 4, 3],
                'room_types': [
                    {'value': value, 'label': label} for value, label in Room.RoomType.choices
                ],
                'amenities': AmenitySerializer(
                    Amenity.objects.filter(is_active=True).annotate(
                        hotel_count=Count('hotels', distinct=True)
                    ),
                    many=True,
                ).data,
                'section': TextSectionSerializer(section, context={'request': request}).data if section else None,
            }
        )

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def featured(self, request):
        queryset = self.get_queryset().filter(is_featured=True)[:8]
        serializer = HotelListSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def availability(self, request, slug=None):
        """Per-room availability for an entire hotel across a date range."""
        hotel = self.get_object()
        check_in = parse_date(request.query_params.get('check_in'))
        check_out = parse_date(request.query_params.get('check_out'))
        if not check_in or not check_out or check_out <= check_in:
            return Response(
                {'detail': 'Provide a valid check_in and check_out (YYYY-MM-DD).'}, status=400
            )

        results = []
        for room in hotel.rooms.filter(is_active=True):
            available, rooms_left = room_availability_for_range(room, check_in, check_out)
            results.append(
                {
                    'room': room.id,
                    'name': room.name,
                    'rooms_left': rooms_left,
                    'is_available': available,
                    'price_per_night': str(room.price_per_night),
                }
            )
        return Response(
            {'check_in': check_in, 'check_out': check_out, 'nights': nights_between(check_in, check_out), 'rooms': results}
        )


class RoomViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RoomSerializer
    permission_classes = [AllowAny]
    queryset = Room.objects.filter(is_active=True, hotel__is_active=True).select_related('hotel')

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related('images', 'amenity_list')
        hotel_slug = self.request.query_params.get('hotel')
        if hotel_slug:
            queryset = queryset.filter(hotel__slug=hotel_slug)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def availability(self, request, pk=None):
        """Quote for a single room: availability, nights, subtotal, tax, total."""
        room = self.get_object()
        check_in = parse_date(request.query_params.get('check_in'))
        check_out = parse_date(request.query_params.get('check_out'))
        guests = request.query_params.get('guests')

        if not check_in or not check_out or check_out <= check_in:
            return Response({'detail': 'Provide a valid check_in and check_out (YYYY-MM-DD).'}, status=400)

        try:
            guest_count = int(guests) if guests else room.capacity
        except ValueError:
            guest_count = room.capacity

        # Guests are the input; the number of rooms is derived from how many
        # guests a single room sleeps, so the customer never has to work it out.
        try:
            room_count = max(1, int(request.query_params.get('rooms') or 1))
        except ValueError:
            room_count = 1

        per_room = max(room.max_guests or 1, 1)
        suggested_rooms = max(1, -(-max(guest_count, 1) // per_room))

        available, rooms_left = room_availability_for_range(room, check_in, check_out)
        enough_rooms = rooms_left >= room_count
        fits_guests = guest_count <= per_room * room_count

        nights = nights_between(check_in, check_out)
        site = SiteSettings.load()
        subtotal = room.price_per_night * nights * room_count
        tax_amount = (subtotal * (site.tax_percentage or 0) / Decimal('100')).quantize(Decimal('0.01'))

        if not available:
            message = 'No rooms of this type are available for the selected dates.'
        elif not enough_rooms:
            message = f'Only {rooms_left} room(s) of this type are left for your dates.'
        else:
            message = f'{rooms_left} room(s) left for your dates.'

        return Response(
            {
                'room': RoomSerializer(room, context={'request': request}).data,
                'check_in': check_in,
                'check_out': check_out,
                'nights': nights,
                'guests': guest_count,
                'rooms': room_count,
                'rooms_count': room_count,
                'suggested_rooms': suggested_rooms,
                'max_rooms': rooms_left,
                'guests_per_room': per_room,
                'fits_guests': fits_guests,
                'is_available': available and enough_rooms and fits_guests,
                'rooms_left': rooms_left,
                'price_per_night': str(room.price_per_night),
                'subtotal': str(subtotal),
                'tax_amount': str(tax_amount),
                'total_price': str(subtotal + tax_amount),
                'currency_symbol': site.currency_symbol,
                'message': message,
            }
        )


class AvailabilitySearchView(viewsets.ViewSet):
    """Cross-hotel availability search: which hotels have space for dates/guests."""

    permission_classes = [AllowAny]

    def list(self, request):
        check_in = parse_date(request.query_params.get('check_in'))
        check_out = parse_date(request.query_params.get('check_out'))
        if not check_in or not check_out or check_out <= check_in:
            return Response({'detail': 'Provide a valid check_in and check_out (YYYY-MM-DD).'}, status=400)

        try:
            guests = int(request.query_params.get('guests', 1))
        except ValueError:
            guests = 1

        city = request.query_params.get('city')
        hotels = Hotel.objects.filter(is_active=True).prefetch_related('rooms')
        if city and city.lower() != 'all':
            hotels = hotels.filter(city__iexact=city)

        results = []
        for hotel in hotels:
            rooms = [
                room for room in hotel.rooms.filter(is_active=True)
                if room.max_guests >= guests
                and room_availability_for_range(room, check_in, check_out)[0]
            ]
            if rooms:
                results.append(
                    {
                        'hotel': HotelListSerializer(hotel, context={'request': request}).data,
                        'cheapest_room': min(rooms, key=lambda r: r.price_per_night).name,
                        'available_rooms': len(rooms),
                    }
                )
        return Response(
            {
                'check_in': check_in,
                'check_out': check_out,
                'nights': nights_between(check_in, check_out),
                'guests': guests,
                'count': len(results),
                'results': results,
            }
        )


class TodayView(viewsets.ViewSet):
    """Tiny utility used by the frontend to default date pickers."""

    permission_classes = [AllowAny]

    def list(self, request):
        return Response({'today': date.today().isoformat()})
