from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase, APITransactionTestCase

from bookings.models import Booking, Payment
from hotels.models import Hotel, Room

User = get_user_model()


class BookingApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.hotel = Hotel.objects.create(
            name='Grand Vista Resort', city='Bali', country='Indonesia', price_per_night='120.00',
        )
        cls.room = Room.objects.create(
            hotel=cls.hotel, name='Deluxe Room', room_type=Room.RoomType.DELUXE,
            price_per_night='120.00', capacity=2, max_guests=3, total_rooms=2,
        )
        cls.user = User.objects.create_user(username='guest', email='guest@example.com', password='pass-1234')
        cls.other = User.objects.create_user(username='other', email='other@example.com', password='pass-1234')

    def setUp(self):
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.check_in = self.today + timedelta(days=7)
        self.check_out = self.check_in + timedelta(days=3)

    def _payload(self, **overrides):
        payload = {
            'room': self.room.id,
            'check_in': self.check_in.isoformat(),
            'check_out': self.check_out.isoformat(),
            'guests': 2,
            'rooms_count': 1,
        }
        payload.update(overrides)
        return payload

    def test_booking_requires_authentication(self):
        self.client.credentials()
        response = self.client.post(reverse('booking-list'), self._payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_booking_prices_the_stay(self):
        response = self.client.post(reverse('booking-list'), self._payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        self.assertTrue(response.data['reference'].startswith('SKY-'))
        self.assertEqual(response.data['nights'], 3)
        self.assertEqual(response.data['subtotal'], '360.00')
        self.assertEqual(response.data['total_price'], '360.00')
        self.assertEqual(response.data['status'], Booking.Status.PENDING)
        self.assertEqual(response.data['room_detail']['hotel_name'], 'Grand Vista Resort')
        # Guest details default to the signed-in customer.
        self.assertEqual(response.data['guest_email'], 'guest@example.com')

    def test_create_booking_rejects_past_check_in(self):
        response = self.client.post(
            reverse('booking-list'),
            self._payload(check_in=(self.today - timedelta(days=1)).isoformat()),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('check_in', response.data)

    def test_create_booking_rejects_checkout_before_checkin(self):
        response = self.client.post(
            reverse('booking-list'), self._payload(check_out=self.check_in.isoformat()), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('check_out', response.data)

    def test_create_booking_rejects_more_guests_than_room_allows(self):
        response = self.client.post(reverse('booking-list'), self._payload(guests=9), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('guests', response.data)

    def test_overbooking_is_rejected_once_inventory_is_gone(self):
        first = self.client.post(reverse('booking-list'), self._payload(rooms_count=2), format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = self.client.post(reverse('booking-list'), self._payload(rooms_count=1), format='json')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('room', second.data)

    def test_non_overlapping_dates_can_be_booked(self):
        self.client.post(reverse('booking-list'), self._payload(rooms_count=2), format='json')
        later_in = self.check_in + timedelta(days=5)
        response = self.client.post(
            reverse('booking-list'),
            self._payload(check_in=later_in.isoformat(), check_out=(later_in + timedelta(days=2)).isoformat()),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_list_only_returns_own_bookings(self):
        Booking.objects.create(
            user=self.other, room=self.room, check_in=self.check_in, check_out=self.check_out,
            guests=1, guest_name='Other', guest_email='other@example.com',
        )
        mine = self.client.post(reverse('booking-list'), self._payload(), format='json')
        response = self.client.get(reverse('booking-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['reference'], mine.data['reference'])

    def test_booking_history_is_ordered_by_stay_date_descending(self):
        # Created out of order so a `created_at` sort would scramble them:
        # the oldest stay is written last, like an imported/seeded batch.
        for offset in (3, 10, 2):
            Booking.objects.create(
                user=self.user,
                room=self.room,
                check_in=self.today + timedelta(days=offset),
                check_out=self.today + timedelta(days=offset + 2),
                guests=1,
                guest_name='Guest',
                guest_email='guest@example.com',
            )

        response = self.client.get(reverse('booking-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stays = [row['check_in'] for row in response.data['results']]
        self.assertEqual(stays, sorted(stays, reverse=True))
        # The furthest-out stay leads and the earliest stay trails.
        self.assertEqual(stays[0], (self.today + timedelta(days=10)).isoformat())
        self.assertEqual(stays[-1], (self.today + timedelta(days=2)).isoformat())

    def test_retrieve_by_reference(self):
        created = self.client.post(reverse('booking-list'), self._payload(), format='json')
        response = self.client.get(reverse('booking-detail', args=[created.data['reference']]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['reference'], created.data['reference'])

    def test_customer_cannot_see_another_users_booking(self):
        mine = Booking.objects.create(
            user=self.other, room=self.room, check_in=self.check_in, check_out=self.check_out,
            guests=1, guest_name='Other', guest_email='other@example.com',
        )
        response = self.client.get(reverse('booking-detail', args=[mine.reference]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_sets_status_and_frees_inventory(self):
        created = self.client.post(reverse('booking-list'), self._payload(rooms_count=2), format='json')
        response = self.client.post(reverse('booking-cancel', args=[created.data['reference']]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Booking.Status.CANCELLED)

        # Inventory is free again, so the same dates can be rebooked.
        again = self.client.post(reverse('booking-list'), self._payload(rooms_count=2), format='json')
        self.assertEqual(again.status_code, status.HTTP_201_CREATED)

    def test_cancelling_twice_is_rejected(self):
        created = self.client.post(reverse('booking-list'), self._payload(), format='json')
        self.client.post(reverse('booking-cancel', args=[created.data['reference']]))
        response = self.client.post(reverse('booking-cancel', args=[created.data['reference']]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_cannot_set_status_directly(self):
        created = self.client.post(reverse('booking-list'), self._payload(), format='json')
        response = self.client.patch(
            reverse('booking-detail', args=[created.data['reference']]),
            {'status': Booking.Status.COMPLETED, 'special_requests': 'Late check-in'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], Booking.Status.PENDING)
        self.assertEqual(response.data['special_requests'], 'Late check-in')

    def test_summary_reports_dashboard_counters(self):
        upcoming = self.client.post(reverse('booking-list'), self._payload(), format='json')
        self.assertEqual(upcoming.status_code, status.HTTP_201_CREATED)

        past_in = self.today - timedelta(days=30)
        Booking.objects.create(
            user=self.user, room=self.room, check_in=past_in, check_out=past_in + timedelta(days=2),
            guests=1, guest_name='Guest', guest_email='guest@example.com',
            status=Booking.Status.COMPLETED,
        )

        response = self.client.get(reverse('booking-summary'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stats']['total_bookings'], 2)
        self.assertEqual(response.data['stats']['upcoming_stays'], 1)
        self.assertEqual(response.data['stats']['completed_stays'], 1)
        self.assertEqual(len(response.data['upcoming']), 1)
        self.assertEqual(len(response.data['recent']), 1)


@override_settings(BOOKING_NOTIFICATION_EMAIL='frontdesk@example.com')
class BookingEmailTests(APITestCase):
    """Reservation email: guest receipt, front-desk notice, failure isolation."""

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.hotel = Hotel.objects.create(
            name='Grand Vista Resort', city='Bali', country='Indonesia', price_per_night='120.00',
        )
        cls.room = Room.objects.create(
            hotel=cls.hotel, name='Deluxe Room', room_type=Room.RoomType.DELUXE,
            price_per_night='120.00', capacity=2, max_guests=3, total_rooms=2,
        )
        cls.user = User.objects.create_user(username='guest', email='guest@example.com', password='pass-1234')

    def setUp(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.check_in = self.today + timedelta(days=7)

    def _payload(self, **overrides):
        payload = {
            'room': self.room.id,
            'check_in': self.check_in.isoformat(),
            'check_out': (self.check_in + timedelta(days=3)).isoformat(),
            'guests': 2,
            'rooms_count': 1,
        }
        payload.update(overrides)
        return payload

    def test_online_booking_is_not_announced_as_confirmed_before_payment(self):
        """The Razorpay window opens right after this call — nobody is "confirmed" yet."""
        response = self.client.post(reverse('booking-list'), self._payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['status'], Booking.Status.PENDING)
        self.assertEqual(response.data['payment_status'], Booking.PaymentStatus.UNPAID)

        # No guest receipt and no front-desk notice until the money is captured.
        self.assertEqual(mail.outbox, [])

    def test_cash_booking_is_reserved_with_payment_pending(self):
        response = self.client.post(
            reverse('booking-list'), self._payload(payment_method='cash'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        reference = response.data['reference']

        guest_mail = next(m for m in mail.outbox if 'guest@example.com' in m.to)
        self.assertIn('reserved', guest_mail.subject.lower())
        self.assertIn('payment pending', guest_mail.subject.lower())
        self.assertIn(reference, guest_mail.body)
        self.assertIn('payment pending', guest_mail.body.lower())
        # Multipart: a plain-text fallback plus the branded HTML version.
        self.assertEqual([mimetype for _, mimetype in guest_mail.alternatives], ['text/html'])

        desk_mail = next(m for m in mail.outbox if m.to == ['frontdesk@example.com'])
        self.assertIn(reference, desk_mail.subject)

    def test_cancelling_a_booking_emails_the_guest(self):
        created = self.client.post(reverse('booking-list'), self._payload(), format='json')
        mail.outbox.clear()

        response = self.client.post(reverse('booking-cancel', args=[created.data['reference']]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('cancelled', mail.outbox[0].subject.lower())
        self.assertIn(created.data['reference'], mail.outbox[0].body)

    def test_a_broken_mail_server_never_breaks_the_booking(self):
        with mock.patch('bookings.emails.EmailMultiAlternatives.send', side_effect=OSError('smtp down')):
            response = self.client.post(
                reverse('booking-list'), self._payload(payment_method='cash'), format='json'
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(mail.outbox, [])


class PaymentAndAdminEmailTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.hotel = Hotel.objects.create(name='Grand Vista Resort', city='Bali', country='Indonesia', price_per_night='100.00')
        cls.room = Room.objects.create(
            hotel=cls.hotel, name='Deluxe Room', room_type=Room.RoomType.DELUXE,
            price_per_night='100.00', capacity=2, max_guests=3, total_rooms=2,
        )
        cls.user = User.objects.create_user(username='guest', email='guest@example.com', password='pass-1234')
        cls.admin = User.objects.create_superuser(username='admin', email='admin@example.com', password='admin-pass')

    def setUp(self):
        self.token = Token.objects.create(user=self.user)
        self.admin_token = Token.objects.create(user=self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.booking = Booking.objects.create(
            user=self.user,
            room=self.room,
            check_in=self.today + timedelta(days=5),
            check_out=self.today + timedelta(days=7),
            guests=2,
            rooms_count=1,
            guest_name='Guest',
            guest_email='guest@example.com',
        )

    def test_create_razorpay_order(self):
        url = reverse('payment-create-order')
        response = self.client.post(url, {'booking_reference': self.booking.reference}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIn('order_id', response.data)
        self.assertEqual(response.data['currency'], 'INR')

    def test_verify_razorpay_payment(self):
        order_url = reverse('payment-create-order')
        order_res = self.client.post(order_url, {'booking_reference': self.booking.reference}, format='json')
        order_id = order_res.data['order_id']

        verify_url = reverse('payment-verify')
        verify_res = self.client.post(
            verify_url,
            {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': 'pay_test123',
                'razorpay_signature': 'sig_test123',
            },
            format='json',
        )
        self.assertEqual(verify_res.status_code, status.HTTP_200_OK, verify_res.data)
        self.assertEqual(verify_res.data['payment_status'], 'paid')
        self.assertEqual(verify_res.data['status'], Booking.Status.CONFIRMED)

        # The money is in — only now does the guest get a confirmation.
        guest_mail = next(m for m in mail.outbox if 'guest@example.com' in m.to)
        self.assertIn('confirmed', guest_mail.subject.lower())
        self.assertIn(self.booking.reference, guest_mail.subject)

    def test_admin_test_email_endpoint(self):
        url = reverse('admin-test-email')
        # Non-admin rejected
        res = self.client.post(url, {'email': 'test@example.com'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin allowed
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.admin_token.key}')
        mail.outbox.clear()
        res_admin = self.client.post(url, {'email': 'test@example.com'}, format='json')
        self.assertEqual(res_admin.status_code, status.HTTP_200_OK, res_admin.data)
        self.assertTrue(res_admin.data['success'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('test@example.com', mail.outbox[0].to)

    def test_create_cash_booking(self):
        from datetime import date, timedelta
        from decimal import Decimal

        url = reverse('booking-list')
        data = {
            'room': self.room.id,
            'check_in': (date.today() + timedelta(days=10)).isoformat(),
            'check_out': (date.today() + timedelta(days=12)).isoformat(),
            'guests': 2,
            'rooms_count': 1,
            'payment_method': 'cash',
        }
        res = self.client.post(url, data, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['status'], Booking.Status.CONFIRMED)
        self.assertEqual(res.data['payment_status'], Booking.PaymentStatus.UNPAID)
        self.assertEqual(res.data['payment_provider'], 'cash')
        self.assertEqual(res.data['cash_received'], '0.00')

        booking = Booking.objects.get(reference=res.data['reference'])
        self.assertTrue(hasattr(booking, 'payment'))
        payment = booking.payment
        self.assertEqual(payment.provider, 'cash')
        self.assertEqual(payment.status, Payment.Status.CREATED)
        self.assertEqual(payment.cash_received, Decimal('0'))

    def test_cash_payment_status_sync(self):
        from datetime import date, timedelta
        from decimal import Decimal

        url = reverse('booking-list')
        data = {
            'room': self.room.id,
            'check_in': (date.today() + timedelta(days=15)).isoformat(),
            'check_out': (date.today() + timedelta(days=17)).isoformat(),
            'guests': 2,
            'rooms_count': 1,
            'payment_method': 'cash',
        }
        res = self.client.post(url, data, format='json')
        booking = Booking.objects.get(reference=res.data['reference'])
        payment = booking.payment

        # ₹0 cash received (Accepted -> unpaid/created)
        payment.cash_received = Decimal('0')
        payment.save()
        booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.CREATED)
        self.assertEqual(booking.payment_status, Booking.PaymentStatus.UNPAID)
        self.assertEqual(payment.cash_remaining, payment.amount)

        # Partial cash payment (₹100 for ₹240 total -> partially_paid)
        payment.cash_received = Decimal('100.00')
        payment.save()
        booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PARTIALLY_PAID)
        self.assertEqual(booking.payment_status, Booking.PaymentStatus.PARTIALLY_PAID)
        self.assertEqual(payment.cash_remaining, payment.amount - Decimal('100.00'))

        # Full cash payment (Equal to amount -> paid)
        payment.cash_received = payment.amount
        payment.save()
        booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(booking.payment_status, Booking.PaymentStatus.PAID)
        self.assertEqual(payment.cash_remaining, Decimal('0'))
        self.assertIsNotNone(payment.paid_at)

    def test_cash_validation_rejections(self):
        from datetime import date, timedelta
        from decimal import Decimal
        from django.core.exceptions import ValidationError

        url = reverse('booking-list')
        data = {
            'room': self.room.id,
            'check_in': (date.today() + timedelta(days=20)).isoformat(),
            'check_out': (date.today() + timedelta(days=22)).isoformat(),
            'guests': 2,
            'rooms_count': 1,
            'payment_method': 'cash',
        }
        res = self.client.post(url, data, format='json')
        booking = Booking.objects.get(reference=res.data['reference'])
        payment = booking.payment

        # Negative cash received (-₹1) -> rejected
        payment.cash_received = Decimal('-1.00')
        with self.assertRaises(ValidationError):
            payment.save()

        # Cash received greater than payment amount (₹241 for ₹240 total) -> rejected
        payment.cash_received = payment.amount + Decimal('1.00')
        with self.assertRaises(ValidationError):
            payment.save()

class BookingConcurrencyTests(APITransactionTestCase):
    def setUp(self):
        self.hotel = Hotel.objects.create(
            name='Concurrency Hotel Resort', city='Bali', country='Indonesia', price_per_night='200.00',
        )
        self.user = User.objects.create_user(username='concurrency_user', email='concurrency@example.com', password='pass-1234')

    def test_availability_concurrency_and_inventory_protection(self):
        import concurrent.futures
        import threading
        from datetime import date, timedelta
        from decimal import Decimal
        from django.db import connections
        from rest_framework.test import APIClient
        from core.utils import room_availability_for_range

        # Create a 1-room capacity room type to test exact zero-availability blocking under race conditions
        single_room = Room.objects.create(
            hotel=self.hotel,
            name='Single Deluxe Concurrency Suite',
            room_type='deluxe',
            total_rooms=1,
            capacity=2,
            price_per_night=Decimal('200.00'),
        )

        d1 = date.today() + timedelta(days=40)
        d3 = date.today() + timedelta(days=43)
        url = reverse('booking-list')

        payload = {
            'room': single_room.id,
            'check_in': d1.isoformat(),
            'check_out': d3.isoformat(),
            'guests': 2,
            'rooms_count': 1,
            'payment_method': 'cash',
        }

        results = []
        user = self.user

        def make_concurrent_booking(index):
            connections.close_all()
            client = APIClient()
            client.force_authenticate(user=user)

            if index == 1:
                import time
                time.sleep(0.02)

            try:
                response = client.post(url, payload, format='json')
                return response.status_code, response.data
            finally:
                connections.close_all()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(make_concurrent_booking, i) for i in range(2)]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        status_codes = [r[0] for r in results]
        successful_bookings = sum(1 for s in status_codes if s == status.HTTP_201_CREATED)
        rejected_bookings = sum(1 for s in status_codes if s == status.HTTP_400_BAD_REQUEST)

        # Assert exactly ONE booking succeeds and exactly ONE booking is rejected due to zero remaining inventory
        self.assertEqual(len(results), 2)
        self.assertEqual(successful_bookings, 1, f"Expected 1 successful booking, got {successful_bookings}. Status codes: {status_codes}")
        self.assertEqual(rejected_bookings, 1, f"Expected 1 rejected booking, got {rejected_bookings}. Status codes: {status_codes}")

        # Assert total active bookings consuming inventory is exactly 1
        active_bookings_count = Booking.objects.filter(
            room=single_room,
            check_in=d1,
            check_out=d3,
            status__in=Booking.BLOCKING_STATUSES,
        ).count()
        self.assertEqual(active_bookings_count, 1)

        # Assert final availability reaches zero
        avail, rooms_left = room_availability_for_range(single_room, d1, d3)
        self.assertFalse(avail)
        self.assertEqual(rooms_left, 0)




