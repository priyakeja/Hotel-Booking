from django.urls import include, path
from rest_framework.routers import DefaultRouter

from hotels.views import AvailabilitySearchView, HotelViewSet, RoomViewSet, TodayView

router = DefaultRouter()
router.register('hotels', HotelViewSet, basename='hotel')
router.register('rooms', RoomViewSet, basename='room')
router.register('availability', AvailabilitySearchView, basename='availability-search')

urlpatterns = [
    path('', include(router.urls)),
]
