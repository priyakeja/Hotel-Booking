from django.urls import include, path
from rest_framework.routers import DefaultRouter

from bookings.views import (
    AdminTestEmailView,
    BookingViewSet,
    CreateRazorpayOrderView,
    VerifyRazorpayPaymentView,
)

router = DefaultRouter()
router.register('bookings', BookingViewSet, basename='booking')

urlpatterns = [
    path('payments/create-order/', CreateRazorpayOrderView.as_view(), name='payment-create-order'),
    path('payments/verify/', VerifyRazorpayPaymentView.as_view(), name='payment-verify'),
    path('payments/webhook/', VerifyRazorpayPaymentView.as_view(), name='payment-webhook'),
    path('admin/test-email/', AdminTestEmailView.as_view(), name='admin-test-email'),
    path('', include(router.urls)),
]

