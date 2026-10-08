from django.urls import include, path
from rest_framework.routers import DefaultRouter

from content.views import (
    AmenityViewSet,
    ContactMessageCreateView,
    ContactPageView,
    FeatureViewSet,
    HeroBannerViewSet,
    HomePageView,
    NavLinkViewSet,
    SiteSettingsView,
    TestimonialViewSet,
    TextSectionViewSet,
)

router = DefaultRouter()
router.register('nav-links', NavLinkViewSet, basename='navlink')
router.register('heroes', HeroBannerViewSet, basename='hero')
router.register('features', FeatureViewSet, basename='feature')
router.register('amenities', AmenityViewSet, basename='amenity')
router.register('testimonials', TestimonialViewSet, basename='testimonial')
router.register('sections', TextSectionViewSet, basename='section')

urlpatterns = [
    path('settings/', SiteSettingsView.as_view(), name='site-settings'),
    path('home/', HomePageView.as_view(), name='home-payload'),
    # The Contact page reads its settings and posts the form through these two.
    path('contact/', ContactPageView.as_view(), name='contact-page'),
    path('contact/messages/', ContactMessageCreateView.as_view(), name='contact-message-create'),
    path('', include(router.urls)),
]
