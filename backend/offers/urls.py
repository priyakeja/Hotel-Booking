from django.urls import include, path
from rest_framework.routers import DefaultRouter

from offers.views import OfferCategoryViewSet, OffersPageView, OfferViewSet

router = DefaultRouter()
router.register('offers', OfferViewSet, basename='offer')
router.register('offer-categories', OfferCategoryViewSet, basename='offer-category')

urlpatterns = [
    # Must be declared before the router so it wins over the `{slug}` detail route.
    path('offers/page/', OffersPageView.as_view(), name='offers-page'),
    path('', include(router.urls)),
]
