from django.db.models import Avg, Count
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from content.emails import send_contact_message_notice
from content.models import (
    Amenity,
    ContactCard,
    ContactFaq,
    ContactSettings,
    Feature,
    HeroBanner,
    NavLink,
    SiteSettings,
    Testimonial,
    TextSection,
)
from content.serializers import (
    AmenitySerializer,
    ContactCardSerializer,
    ContactFaqSerializer,
    ContactMessageSerializer,
    ContactSettingsSerializer,
    FeatureSerializer,
    HeroBannerSerializer,
    NavLinkSerializer,
    SiteSettingsSerializer,
    TestimonialSerializer,
    TextSectionSerializer,
)
from hotels.models import Hotel
from hotels.serializers import HotelListSerializer


class SiteSettingsView(APIView):
    """Everything the header/footer needs: branding, contact details, nav links."""

    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = SiteSettings.load()
        data = SiteSettingsSerializer(settings_obj, context={'request': request}).data
        data['nav_links'] = NavLinkSerializer(
            NavLink.objects.filter(is_active=True), many=True
        ).data
        return Response(data)


class ContactPageView(APIView):
    """One call that hydrates the whole Contact page.

    Exposing settings, cards and FAQs together means the Contact page *and* the
    footer read the exact same contact details — a single source of truth.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = ContactSettings.load()
        context = {'request': request}
        return Response(
            {
                'settings': ContactSettingsSerializer(settings_obj, context=context).data,
                'cards': ContactCardSerializer(
                    ContactCard.objects.filter(is_active=True), many=True
                ).data,
                'faqs': ContactFaqSerializer(
                    ContactFaq.objects.filter(is_active=True), many=True
                ).data,
            }
        )


class ContactMessageCreateView(APIView):
    """Public endpoint behind the contact form.

    Only creates messages — reading them happens in the Django admin, so guest
    enquiries are never exposed through a public API.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        settings_obj = ContactSettings.load()
        if not settings_obj.contact_form_enabled:
            return Response(
                {'detail': settings_obj.form_error_message or 'The contact form is currently closed.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        # Forward the enquiry to the site inbox. A mail outage must not fail the
        # submission — the message is already stored in the admin either way.
        send_contact_message_notice(message, request)

        return Response(
            {
                'detail': settings_obj.form_success_message,
                'status': message.status,
                'id': message.pk,
            },
            status=status.HTTP_201_CREATED,
        )


class HomePageView(APIView):
    """Single call that hydrates the entire marketing homepage."""

    permission_classes = [AllowAny]

    def get(self, request):
        context = {'request': request}
        settings_obj = SiteSettings.load()

        featured = (
            Hotel.objects.filter(is_active=True, is_featured=True)
            .prefetch_related('images', 'amenities', 'rooms')[:8]
        )
        if not featured:
            featured = Hotel.objects.filter(is_active=True).prefetch_related('rooms')[:8]

        sections = {s.key: TextSectionSerializer(s, context=context).data for s in TextSection.objects.filter(is_active=True)}

        # Real guest-satisfaction numbers for the hero stats (only approved reviews).
        from reviews.models import Review

        reviews = Review.objects.filter(is_approved=True)
        average = reviews.aggregate(value=Avg('rating'))['value']

        return Response(
            {
                'settings': SiteSettingsSerializer(settings_obj, context=context).data,
                'heroes': HeroBannerSerializer(
                    HeroBanner.objects.filter(is_active=True), many=True, context=context
                ).data,
                'features': FeatureSerializer(Feature.objects.filter(is_active=True), many=True).data,
                'featured_hotels': HotelListSerializer(featured, many=True, context=context).data,
                'amenities': AmenitySerializer(
                    Amenity.objects.filter(is_active=True, show_on_homepage=True), many=True
                ).data,
                'testimonials': TestimonialSerializer(
                    Testimonial.objects.filter(is_active=True), many=True, context=context
                ).data,
                'sections': sections,
                'stats': {
                    'hotels': Hotel.objects.filter(is_active=True).count(),
                    'destinations': Hotel.objects.filter(is_active=True).values('city').distinct().count(),
                    'reviews': reviews.count(),
                    'avg_rating': round(float(average), 1) if average is not None else None,
                },
            }
        )


class NavLinkViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NavLinkSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = NavLink.objects.filter(is_active=True)
        location = self.request.query_params.get('location')
        return queryset.filter(location=location) if location else queryset


class HeroBannerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = HeroBannerSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = HeroBanner.objects.filter(is_active=True)


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FeatureSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = Feature.objects.filter(is_active=True)


class AmenityViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AmenitySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = Amenity.objects.filter(is_active=True).annotate(
            hotel_count=Count('hotels', distinct=True)
        )
        if self.request.query_params.get('homepage') == 'true':
            queryset = queryset.filter(show_on_homepage=True)
        return queryset


class TestimonialViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TestimonialSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = Testimonial.objects.filter(is_active=True)


class TextSectionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TextSectionSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    lookup_field = 'key'
    lookup_url_kwarg = 'key'
    queryset = TextSection.objects.filter(is_active=True).prefetch_related('gallery')
