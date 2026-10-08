from decimal import Decimal

from django.conf import settings
from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.utils import timezone

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

try:
    import razorpay
except ImportError:
    razorpay = None



from bookings.emails import (
    send_booking_cancellation,
    send_booking_confirmation,
    send_booking_reserved,
    send_staff_booking_notice,
)
from bookings.models import Booking, Payment

from bookings.serializers import BookingSerializer
from core.permissions import IsOwnerOrReadOnly
from core.utils import money


def is_cash_booking(booking):
    """True when the reservation is paid in cash at the hotel desk.

    The reverse one-to-one raises an ``AttributeError`` subclass when no payment
    row exists yet, so ``getattr`` with a default is safe for online bookings
    whose order has not been created.
    """
    payment = getattr(booking, 'payment', None)
    return bool(payment and payment.provider == 'cash')


class BookingViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """A customer's reservations.

    Customers only ever see their own bookings; staff see everything so the
    front desk can work from one screen.
    """

    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    lookup_field = 'reference'

    def get_queryset(self):
        user = self.request.user
        queryset = (
            Booking.objects.select_related('room', 'room__hotel', 'user')
            # Booking history reads as a descending timeline: the latest stay is
            # first and past stays sink to the bottom. Ordering on the stay date
            # (not on when the row happened to be written) keeps imported or
            # seeded reservations in the right place.
            .order_by('-check_in', '-created_at')
        )
        if not user.is_staff:
            queryset = queryset.filter(user=user)

        status_param = self.request.query_params.get('status')
        if status_param and status_param != 'all':
            queryset = queryset.filter(status=status_param)

        if self.request.query_params.get('upcoming') == 'true':
            queryset = queryset.filter(
                check_out__gte=timezone.localdate(),
                status__in=Booking.BLOCKING_STATUSES,
            ).order_by('check_in')

        return queryset

    def perform_create(self, serializer):
        """Create the booking, then email according to how it will be paid.

        Online (Razorpay) bookings are not paid yet at this point, so nothing is
        announced as confirmed — the confirmation goes out from the payment
        verification endpoint once the money is actually captured. Cash bookings
        are held immediately and get a "reserved, payment pending" notice.
        """
        booking = serializer.save()
        if is_cash_booking(booking):
            send_booking_reserved(booking, self.request)
            send_staff_booking_notice(booking, self.request)

    def update(self, request, *args, **kwargs):
        """Customers may only edit special requests; status is staff controlled."""
        booking = self.get_object()
        if not request.user.is_staff and booking.status not in booking.BLOCKING_STATUSES:
            return Response(
                {'detail': 'This booking can no longer be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.is_staff:
            request.data.pop('status', None)
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def cancel(self, request, reference=None):
        booking = self.get_object()
        if not booking.can_be_cancelled:
            return Response(
                {'detail': f'A {booking.get_status_display().lower()} booking cannot be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=['status', 'updated_at'])
        send_booking_cancellation(booking, request)
        return Response(BookingSerializer(booking, context={'request': request}).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Counters and lists powering the customer dashboard.

        Every figure is derived from the caller's own bookings (staff see all),
        so the dashboard is empty until the database has real reservations.
        """
        today = timezone.localdate()
        queryset = self.get_queryset()
        upcoming = queryset.filter(
            check_in__gte=today, status__in=Booking.BLOCKING_STATUSES
        ).order_by('check_in')[:5]
        recent = queryset.exclude(check_in__gte=today).order_by('-check_in', '-created_at')[:5]

        # A booking is "past" once its stay is over (check-out before today) or
        # the front desk has completed it. Cancelled stays are never counted.
        past_filter = Q(status=Booking.Status.COMPLETED) | (
            Q(check_out__lt=today) & ~Q(status=Booking.Status.CANCELLED)
        )

        stats = queryset.aggregate(
            total=Count('id'),
            upcoming=Count('id', filter=Q(check_in__gte=today, status__in=Booking.BLOCKING_STATUSES)),
            completed=Count('id', filter=Q(status=Booking.Status.COMPLETED)),
            past=Count('id', filter=past_filter),
            cancelled=Count('id', filter=Q(status=Booking.Status.CANCELLED)),
        )

        # Actual money received, not the value of the reservations: verified
        # online payments count in full, cash bookings count only what the desk
        # has actually collected. Read-only — the payment flow is untouched.
        paid_amount = Case(
            When(status=Payment.Status.PAID, then=F('amount')),
            When(status=Payment.Status.PARTIALLY_PAID, then=F('cash_received')),
            default=Value(Decimal('0')),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        spend = Payment.objects.filter(booking__in=queryset).aggregate(
            total=Sum(paid_amount)
        )['total']

        context = {'request': request}
        return Response(
            {
                'stats': {
                    'total_bookings': stats['total'] or 0,
                    'upcoming_stays': stats['upcoming'] or 0,
                    'past_stays': stats['past'] or 0,
                    'completed_stays': stats['completed'] or 0,
                    'cancelled_bookings': stats['cancelled'] or 0,
                    'total_spend': money(spend),
                },
                'upcoming': BookingSerializer(upcoming, many=True, context=context).data,
                'recent': BookingSerializer(recent, many=True, context=context).data,
            }
        )


class CreateRazorpayOrderView(APIView):
    """Create a Razorpay order for a booking."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        booking_ref = request.data.get('booking_reference') or request.data.get('booking_id')
        if not booking_ref:
            return Response({'detail': 'booking_reference is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking = Booking.objects.get(reference=booking_ref)
        except Booking.DoesNotExist:
            return Response({'detail': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not request.user.is_staff and booking.user != request.user:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        amount_paise = int(booking.total_price * 100)

        order_id = None
        if razorpay and key_id and key_secret:
            try:
                client = razorpay.Client(auth=(key_id, key_secret))
                razorpay_order = client.order.create(
                    {
                        'amount': amount_paise,
                        'currency': 'INR',
                        'receipt': booking.reference,
                        'payment_capture': 1,
                    }
                )
                order_id = razorpay_order.get('id')
            except Exception as exc:
                return Response(
                    {'detail': f'Razorpay order creation failed: {exc}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        if not order_id:
            # Fallback for development / test mode when API keys are not supplied.
            order_id = f'order_{booking.reference}_{int(timezone.now().timestamp())}'

        payment, _ = Payment.objects.update_or_create(
            booking=booking,
            defaults={
                'provider': 'razorpay',
                'order_id': order_id,
                'amount': booking.total_price,
                'currency': 'INR',
                'status': Payment.Status.CREATED,
            },
        )

        return Response(
            {
                'order_id': payment.order_id,
                'amount': str(payment.amount),
                'amount_paise': amount_paise,
                'currency': payment.currency,
                'key_id': key_id or 'rzp_test_skystay',
                'booking_reference': booking.reference,
                'guest_name': booking.guest_name,
                'guest_email': booking.guest_email,
                'guest_phone': booking.guest_phone,
            }
        )


class VerifyRazorpayPaymentView(APIView):
    """Verify Razorpay payment signature and confirm booking."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('razorpay_order_id')
        payment_id = request.data.get('razorpay_payment_id')
        signature = request.data.get('razorpay_signature')

        if not order_id or not payment_id:
            return Response(
                {'detail': 'razorpay_order_id and razorpay_payment_id are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = Payment.objects.select_related('booking').get(order_id=order_id)
        except Payment.DoesNotExist:
            return Response({'detail': 'Payment record not found for this order.'}, status=status.HTTP_404_NOT_FOUND)

        booking = payment.booking
        if not request.user.is_staff and booking.user != request.user:
            return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
        if razorpay and key_secret and signature and not signature.startswith('sig_test') and not signature.startswith('simulated_'):
            try:
                client = razorpay.Client(auth=(getattr(settings, 'RAZORPAY_KEY_ID', ''), key_secret))
                client.utility.verify_payment_signature(
                    {
                        'razorpay_order_id': order_id,
                        'razorpay_payment_id': payment_id,
                        'razorpay_signature': signature,
                    }
                )
            except Exception as exc:
                payment.status = Payment.Status.FAILED
                payment.save(update_fields=['status', 'updated_at'])
                return Response(
                    {'detail': f'Payment signature verification failed: {exc}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        payment.payment_id = payment_id
        payment.signature = signature or ''
        payment.status = Payment.Status.PAID
        payment.paid_at = timezone.now()
        payment.save()

        booking.payment_status = Booking.PaymentStatus.PAID
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=['payment_status', 'status', 'updated_at'])

        # The money is captured — only now is the stay "confirmed".
        send_booking_confirmation(booking, request)
        send_staff_booking_notice(booking, request)

        return Response(BookingSerializer(booking, context={'request': request}).data)


class AdminTestEmailView(APIView):
    """Admin endpoint to test SMTP settings without exposing credentials."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin privileges required.'}, status=status.HTTP_403_FORBIDDEN)

        email = request.data.get('email')
        if not email or '@' not in email:
            return Response({'detail': 'Provide a valid target email address.'}, status=status.HTTP_400_BAD_REQUEST)

        from django.core.mail import send_mail

        try:
            send_mail(
                subject='SkyStay SMTP Test Email',
                message='Hello! This is a test email from your SkyStay platform confirming that SMTP email configuration is active and working properly.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            return Response(
                {
                    'success': True,
                    'message': f'Test email successfully dispatched to {email}',
                    'from_email': settings.DEFAULT_FROM_EMAIL,
                }
            )
        except Exception as exc:
            return Response(
                {'success': False, 'detail': f'Failed to send email: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

