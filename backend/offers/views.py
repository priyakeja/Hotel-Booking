from decimal import Decimal

from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import parse_date, room_availability_for_range
from hotels.models import Hotel, Room
from offers.models import Offer, OfferCategory, OfferSettings
from offers.serializers import (
    OfferCardSerializer,
    OfferCategorySerializer,
    OfferDetailSerializer,
    OfferSettingsSerializer,
)

#: How the discount quick-filters are labelled vs the threshold they apply.
DISCOUNT_TIERS = [(10, '10%+'), (20, '20%+'), (30, '30%+'), (50, '50%+')]


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    """Public deals catalogue. Every filter, sort and search is query-param driven."""

    permission_classes = [AllowAny]
    lookup_field = 'slug'
    serializer_class = OfferCardSerializer

    def get_serializer_class(self):
        return OfferDetailSerializer if self.action == 'retrieve' else OfferCardSerializer

    def base_queryset(self):
        return (
            Offer.objects
            .select_related('hotel', 'category')
            .prefetch_related('benefits', 'images', 'rooms', 'hotel__rooms')
        )

    def get_queryset(self):
        # The list only surfaces live offers; the detail page can still be opened
        # for a published-but-expired offer (shown as “Expired” for marketing),
        # but never for drafts or disabled offers.
        if self.action == 'retrieve':
            return self.base_queryset().filter(is_published=True, is_disabled=False)
        return self.base_queryset().live()

    # -- DB level filters -------------------------------------------------
    def apply_filters(self, queryset):
        params = self.request.query_params

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(short_description__icontains=search)
                | Q(description__icontains=search)
                | Q(hotel__name__icontains=search)
                | Q(hotel__city__icontains=search)
                | Q(hotel__country__icontains=search)
            )

        category = params.get('category')
        if category and category.lower() != 'all':
            queryset = queryset.filter(category__slug__in=[c.strip() for c in category.split(',') if c.strip()])

        offer_type = params.get('offer_type')
        if offer_type and offer_type.lower() != 'all':
            queryset = queryset.filter(offer_type__in=[t.strip() for t in offer_type.split(',') if t.strip()])

        destination = params.get('destination') or params.get('city')
        if destination and destination.lower() != 'all':
            queryset = queryset.filter(hotel__city__in=[c.strip() for c in destination.split(',') if c.strip()])

        hotel = params.get('hotel')
        if hotel:
            queryset = queryset.filter(hotel__slug=hotel)

        room_type = params.get('room_type')
        if room_type and room_type.lower() != 'all':
            queryset = queryset.filter(
                Q(rooms__room_type=room_type)
                | Q(rooms__isnull=True, hotel__rooms__room_type=room_type)
            ).distinct()

        benefit_names = params.getlist('benefit') if hasattr(params, 'getlist') else []
        benefit_names = [b for b in (benefit_names or [params.get('benefit')]) if b]
        for name in benefit_names:
            queryset = queryset.filter(benefits__text__iexact=name).distinct()

        if params.get('featured') == 'true':
            queryset = queryset.filter(is_featured=True)

        if params.get('promo') == 'true':
            queryset = queryset.filter(promo_code_enabled=True)

        return queryset

    # -- computed (python) filters ---------------------------------------
    def _needs_python(self, params):
        if params.get('discount'):
            return True
        if params.get('min_price') or params.get('max_price'):
            return True
        if params.get('check_in') and params.get('check_out'):
            return True
        return False

    def _python_filter(self, offers):
        params = self.request.query_params

        discount = params.get('discount')
        if discount:
            try:
                threshold = int(float(discount))
            except (TypeError, ValueError):
                threshold = 0
            offers = [o for o in offers if o.discount_percent >= threshold]

        min_price = params.get('min_price')
        if min_price:
            try:
                floor = Decimal(min_price)
                offers = [o for o in offers if o.offer_price >= floor]
            except (TypeError, ValueError):
                pass
        max_price = params.get('max_price')
        if max_price:
            try:
                ceiling = Decimal(max_price)
                offers = [o for o in offers if o.offer_price <= ceiling]
            except (TypeError, ValueError):
                pass

        check_in = parse_date(params.get('check_in'))
        check_out = parse_date(params.get('check_out'))
        if check_in and check_out:
            keep = []
            for offer in offers:
                if offer.validate_stay(check_in, check_out):
                    continue
                if not any(
                    room_availability_for_range(room, check_in, check_out)[0]
                    for room in offer.applicable_rooms()
                ):
                    continue
                keep.append(offer)
            offers = keep

        return offers

    def _python_sort(self, offers, key):
        if key == 'discount':
            offers.sort(key=lambda o: o.discount_percent, reverse=True)
        elif key == 'price_low':
            offers.sort(key=lambda o: o.offer_price)
        elif key == 'price_high':
            offers.sort(key=lambda o: o.offer_price, reverse=True)
        return offers

    ORDERING_MAP = {
        'recommended': ('display_order', '-is_featured', '-created_at'),
        'ending_soon': ('end_date', 'display_order'),
        'newest': ('-created_at',),
        'value': ('-discount_value',),
    }

    # -- list -------------------------------------------------------------
    def list(self, request, *args, **kwargs):
        queryset = self.apply_filters(self.get_queryset())

        params = request.query_params
        sort_key = params.get('sort') or params.get('ordering') or 'recommended'

        if self._needs_python(params) or sort_key in ('discount', 'price_low', 'price_high'):
            offers = self._python_filter(list(queryset))
            if sort_key in ('discount', 'price_low', 'price_high'):
                offers = self._python_sort(offers, sort_key)
        else:
            offers = queryset.order_by(*self.ORDERING_MAP.get(sort_key, self.ORDERING_MAP['recommended']))

        page = self.paginate_queryset(offers)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(offers, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        offer = self.get_object()
        Offer.objects.filter(pk=offer.pk).update(view_count=offer.view_count + 1)
        return Response(self.get_serializer(offer).data)

    # -- extra list endpoints --------------------------------------------
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Handpicked, live, featured offers — used by the page and the homepage."""
        window = OfferSettings.load().limited_window_days or 7
        offers = self.base_queryset().featured()[:8]
        data = self.get_serializer(offers, many=True).data
        return Response({'count': len(data), 'results': data, 'window_days': window})

    @action(detail=False, methods=['get'])
    def limited(self, request):
        """Live offers whose end date is close — real expiry, never a fake countdown."""
        window = OfferSettings.load().limited_window_days or 7
        offers = list(
            self.base_queryset()
            .ending_soon(window)
            .order_by('end_date', 'display_order')[:8]
        )
        return Response({
            'count': len(offers),
            'results': self.get_serializer(offers, many=True).data,
            'window_days': window,
        })

    @action(detail=False, methods=['get'])
    def categories(self, request):
        categories = (
            OfferCategory.objects.filter(is_active=True)
            .annotate(offer_count=Count('offers', filter=Q(offers__is_published=True)))
        )
        total = Offer.objects.live().count()
        return Response({
            'total': total,
            'results': OfferCategorySerializer(categories, many=True).data,
        })

    @action(detail=False, methods=['get'])
    def filters(self, request):
        """Filter metadata for the Offers sidebar — real database values only."""
        live = Offer.objects.live()
        destinations = (
            Hotel.objects.filter(is_active=True, offers__in=live)
            .values('city', 'country')
            .annotate(total=Count('id', distinct=True))
            .order_by('city')
        )
        benefits = (
            Offer.objects.live()
            .values_list('benefits__text', flat=True)
            .exclude(benefits__text__isnull=True)
            .exclude(benefits__text='')
            .distinct()
            .order_by('benefits__text')
        )
        priced = [o.offer_price for o in live]
        price_bounds = {
            'min': str(min(priced)) if priced else '0',
            'max': str(max(priced)) if priced else '0',
        }
        hotels = (
            Hotel.objects.filter(is_active=True, offers__in=live)
            .values('id', 'name', 'city', 'country')
            .distinct()
            .order_by('name')
        )
        return Response({
            'destinations': [
                {
                    'city': row['city'],
                    'country': row['country'],
                    'label': f"{row['city']}, {row['country']}",
                    'hotels': row['total'],
                }
                for row in destinations
            ],
            'hotels': list(hotels),
            'offer_types': [{'value': v, 'label': l} for v, l in Offer.OfferType.choices],
            'discount_tiers': [{'value': v, 'label': l} for v, l in DISCOUNT_TIERS],
            'room_types': [{'value': v, 'label': l} for v, l in Room.RoomType.choices],
            'benefits': [b for b in benefits if b],
            'price_range': price_bounds,
        })

    @action(detail=True, methods=['post'])
    def track(self, request, slug=None):
        """Lightweight analytics: count views / clicks without a redesign."""
        event = (request.data or {}).get('event', 'view')
        field = {'view': 'view_count', 'click': 'click_count', 'booking': 'booking_count'}.get(event)
        if not field:
            return Response({'detail': 'Unknown event.'}, status=status.HTTP_400_BAD_REQUEST)
        Offer.objects.filter(slug=slug, is_published=True).update(**{field: F(field) + 1})
        return Response({'ok': True, 'event': event})


class OffersPageView(APIView):
    """Single call that hydrates the public Offers page: settings + sections."""

    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = OfferSettings.load()
        context = {'request': request}

        featured = Offer.objects.featured()[:6]
        window = settings_obj.limited_window_days or 7
        limited = Offer.objects.ending_soon(window).order_by('end_date')[:8]

        return Response({
            'settings': OfferSettingsSerializer(settings_obj, context=context).data,
            'featured': OfferCardSerializer(featured, many=True, context=context).data,
            'limited': OfferCardSerializer(limited, many=True, context=context).data,
        })


class OfferCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    serializer_class = OfferCategorySerializer
    pagination_class = None
    lookup_field = 'slug'

    def get_queryset(self):
        return (
            OfferCategory.objects.filter(is_active=True)
            .annotate(offer_count=Count('offers', filter=Q(offers__is_published=True)))
        )
