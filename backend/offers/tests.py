from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from hotels.models import Hotel, Room
from offers.models import Offer, OfferBenefit, OfferCategory

User = get_user_model()


def make_hotel(name='Grand Vista Resort', city='Bali', country='Indonesia', price='120.00'):
    return Hotel.objects.create(
        name=name, city=city, country=country, price_per_night=Decimal(price),
        short_description='Test hotel',
    )


def make_room(hotel, name='Deluxe Ocean View', price='120.00', room_type=Room.RoomType.DELUXE):
    return Room.objects.create(hotel=hotel, name=name, room_type=room_type, price_per_night=Decimal(price))


def make_offer(hotel, **overrides):
    today = timezone.localdate()
    defaults = dict(
        title='Weekend Escape',
        short_description='Stay 2 nights and save 30%',
        hotel=hotel,
        discount_type=Offer.DiscountType.PERCENTAGE,
        discount_value=Decimal('30'),
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=30),
        is_published=True,
        is_featured=False,
    )
    defaults.update(overrides)
    return Offer.objects.create(**defaults)


class OfferPricingTests(APITestCase):
    def test_percentage_discount(self):
        hotel = make_hotel()
        make_room(hotel, price='120.00')
        offer = make_offer(hotel, discount_value=Decimal('30'))
        self.assertEqual(offer.base_price, Decimal('120.00'))
        self.assertEqual(offer.offer_price, Decimal('84.00'))
        self.assertEqual(offer.saving, Decimal('36.00'))
        self.assertEqual(offer.discount_percent, 30)

    def test_fixed_discount(self):
        hotel = make_hotel()
        make_room(hotel, price='5000.00')
        offer = make_offer(hotel, discount_type=Offer.DiscountType.FIXED, discount_value=Decimal('1500'))
        self.assertEqual(offer.offer_price, Decimal('3500.00'))
        self.assertEqual(offer.saving, Decimal('1500.00'))

    def test_special_price(self):
        hotel = make_hotel()
        make_room(hotel, price='5000.00')
        offer = make_offer(
            hotel, discount_type=Offer.DiscountType.SPECIAL_PRICE, discount_value=Decimal('2999'),
        )
        self.assertEqual(offer.offer_price, Decimal('2999.00'))

    def test_free_night_keeps_rate(self):
        hotel = make_hotel()
        make_room(hotel, price='120.00')
        offer = make_offer(
            hotel, discount_type=Offer.DiscountType.FREE_NIGHT, discount_value=Decimal('0'), free_nights=1,
        )
        self.assertEqual(offer.offer_price, Decimal('120.00'))
        self.assertEqual(offer.free_nights, 1)

    def test_original_price_override(self):
        hotel = make_hotel()
        make_room(hotel, price='120.00')
        offer = make_offer(hotel, original_price=Decimal('200.00'), discount_value=Decimal('25'))
        self.assertEqual(offer.base_price, Decimal('200.00'))
        self.assertEqual(offer.offer_price, Decimal('150.00'))

    def test_cheapest_eligible_room_drives_base_price(self):
        hotel = make_hotel()
        make_room(hotel, name='Standard', price='100.00')
        make_room(hotel, name='Suite', price='300.00', room_type=Room.RoomType.SUITE)
        offer = make_offer(hotel)
        self.assertEqual(offer.base_price, Decimal('100.00'))


class OfferStatusTests(APITestCase):
    def setUp(self):
        self.hotel = make_hotel()
        make_room(self.hotel)

    def test_draft_when_not_published(self):
        offer = make_offer(self.hotel, is_published=False)
        self.assertEqual(offer.status, Offer.Status.DRAFT)

    def test_scheduled_in_future(self):
        today = timezone.localdate()
        offer = make_offer(self.hotel, start_date=today + timedelta(days=3), end_date=today + timedelta(days=10))
        self.assertEqual(offer.status, Offer.Status.SCHEDULED)

    def test_active_window(self):
        offer = make_offer(self.hotel)
        self.assertEqual(offer.status, Offer.Status.ACTIVE)

    def test_expired(self):
        today = timezone.localdate()
        offer = make_offer(self.hotel, start_date=today - timedelta(days=10), end_date=today - timedelta(days=1))
        self.assertEqual(offer.status, Offer.Status.EXPIRED)

    def test_disabled_overrides_dates(self):
        offer = make_offer(self.hotel, is_disabled=True)
        self.assertEqual(offer.status, Offer.Status.DISABLED)


class OfferApiTests(APITestCase):
    def setUp(self):
        self.hotel = make_hotel()
        make_room(self.hotel)

    def test_list_only_returns_live_offers(self):
        make_offer(self.hotel, title='Live Deal')
        today = timezone.localdate()
        make_offer(self.hotel, title='Old Deal', start_date=today - timedelta(days=20), end_date=today - timedelta(days=5))
        make_offer(self.hotel, title='Draft Deal', is_published=False)

        response = self.client.get(reverse('offer-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [row['title'] for row in response.data['results']]
        self.assertEqual(titles, ['Live Deal'])

    def test_card_payload_contains_discount_fields(self):
        make_offer(self.hotel, discount_value=Decimal('30'))
        response = self.client.get(reverse('offer-list'))
        card = response.data['results'][0]
        self.assertEqual(card['discount_type'], 'percentage')
        self.assertEqual(card['discount_percent'], 30)
        self.assertEqual(card['original_price'], '120.00')
        self.assertEqual(card['offer_price'], '84.00')
        self.assertEqual(card['saving'], '36.00')
        self.assertEqual(card['hotel']['name'], 'Grand Vista Resort')
        self.assertIn('valid_until', card)

    def test_search_matches_hotel_and_title(self):
        make_offer(self.hotel, title='Weekend Escape')
        other = make_hotel(name='Beach House', city='Goa', country='India')
        make_room(other)
        make_offer(other, title='Early Bird', offer_type=Offer.OfferType.EARLY_BIRD)

        by_title = self.client.get(reverse('offer-list'), {'search': 'Weekend'})
        self.assertEqual([r['title'] for r in by_title.data['results']], ['Weekend Escape'])

        by_city = self.client.get(reverse('offer-list'), {'search': 'Goa'})
        self.assertEqual([r['title'] for r in by_city.data['results']], ['Early Bird'])

    def test_filter_by_category_and_type(self):
        category = OfferCategory.objects.create(name='Weekend')
        make_offer(self.hotel, title='Weekend Escape', category=category)
        make_offer(self.hotel, title='Early Bird', offer_type=Offer.OfferType.EARLY_BIRD)

        by_cat = self.client.get(reverse('offer-list'), {'category': category.slug})
        self.assertEqual([r['title'] for r in by_cat.data['results']], ['Weekend Escape'])

        by_type = self.client.get(reverse('offer-list'), {'offer_type': 'early_bird'})
        self.assertEqual([r['title'] for r in by_type.data['results']], ['Early Bird'])

    def test_discount_threshold_filter(self):
        make_offer(self.hotel, title='Small', discount_value=Decimal('10'))
        make_offer(self.hotel, title='Big', discount_value=Decimal('40'))

        response = self.client.get(reverse('offer-list'), {'discount': '30'})
        self.assertEqual([r['title'] for r in response.data['results']], ['Big'])

    def test_sort_by_highest_discount(self):
        make_offer(self.hotel, title='Small', discount_value=Decimal('10'))
        make_offer(self.hotel, title='Big', discount_value=Decimal('40'))
        response = self.client.get(reverse('offer-list'), {'sort': 'discount'})
        self.assertEqual([r['title'] for r in response.data['results']], ['Big', 'Small'])

    def test_featured_endpoint_only_live_featured(self):
        make_offer(self.hotel, title='Featured', is_featured=True)
        make_offer(self.hotel, title='Plain', is_featured=False)
        response = self.client.get(reverse('offer-featured'))
        self.assertEqual([r['title'] for r in response.data['results']], ['Featured'])

    def test_limited_endpoint_returns_ending_soon(self):
        today = timezone.localdate()
        make_offer(self.hotel, title='Ending', end_date=today + timedelta(days=2))
        make_offer(self.hotel, title='Later', end_date=today + timedelta(days=60))
        response = self.client.get(reverse('offer-limited'))
        self.assertEqual([r['title'] for r in response.data['results']], ['Ending'])

    def test_detail_returns_benefits_terms_and_rooms(self):
        offer = make_offer(self.hotel)
        OfferBenefit.objects.create(offer=offer, text='Free Breakfast')
        offer.terms = 'Minimum 2-night stay.\nSubject to availability.'
        offer.save()

        response = self.client.get(reverse('offer-detail', kwargs={'slug': offer.slug}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['benefits'][0]['text'], 'Free Breakfast')
        self.assertEqual(response.data['terms'], ['Minimum 2-night stay.', 'Subject to availability.'])
        self.assertEqual(response.data['rooms'][0]['name'], 'Deluxe Ocean View')

    def test_expired_offer_detail_is_labelled(self):
        today = timezone.localdate()
        offer = make_offer(self.hotel, start_date=today - timedelta(days=10), end_date=today - timedelta(days=1))
        response = self.client.get(reverse('offer-detail', kwargs={'slug': offer.slug}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'expired')

    def test_page_payload_has_settings_and_sections(self):
        make_offer(self.hotel, is_featured=True)
        response = self.client.get(reverse('offers-page'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('settings', response.data)
        self.assertIn('featured', response.data)
        self.assertIn('limited', response.data)


class OfferBookingTests(APITestCase):
    def setUp(self):
        self.hotel = make_hotel()
        self.room = make_room(self.hotel, price='100.00')
        self.user = User.objects.create_user(username='guest', email='guest@example.com', password='secret-pass-1')
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.today = timezone.localdate()

    def _payload(self, offer, check_in, check_out):
        return {
            'room': self.room.id,
            'offer': offer.slug,
            'check_in': check_in.isoformat(),
            'check_out': check_out.isoformat(),
            'guests': 2,
            'rooms_count': 1,
        }

    def test_booking_applies_offer_price_server_side(self):
        offer = make_offer(self.hotel, discount_value=Decimal('30'), min_stay=1)
        check_in = self.today + timedelta(days=3)
        check_out = check_in + timedelta(days=2)

        response = self.client.post(reverse('booking-list'), self._payload(offer, check_in, check_out), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['price_per_night'], '70.00')
        self.assertEqual(response.data['offer_slug'], offer.slug)

        offer.refresh_from_db()
        self.assertEqual(offer.booking_count, 1)

    def test_booking_rejects_expired_offer(self):
        offer = make_offer(self.hotel, start_date=self.today - timedelta(days=10), end_date=self.today - timedelta(days=1))
        response = self.client.post(
            reverse('booking-list'),
            self._payload(offer, self.today + timedelta(days=1), self.today + timedelta(days=3)),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('offer', response.data)

    def test_booking_rejects_min_stay_violation(self):
        offer = make_offer(self.hotel, min_stay=3)
        response = self.client.post(
            reverse('booking-list'),
            self._payload(offer, self.today + timedelta(days=2), self.today + timedelta(days=3)),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('offer', response.data)

    def test_booking_rejects_ineligible_room(self):
        offer = make_offer(self.hotel)
        other_room = make_room(self.hotel, name='Standard', price='90.00')
        offer.rooms.add(self.room)  # only the deluxe room is eligible

        payload = self._payload(offer, self.today + timedelta(days=2), self.today + timedelta(days=4))
        payload['room'] = other_room.id
        response = self.client.post(reverse('booking-list'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('offer', response.data)

    def test_booking_rejects_offer_for_other_hotel(self):
        other_hotel = make_hotel(name='Beach House', city='Goa', country='India')
        other_offer = make_offer(other_hotel)
        response = self.client.post(
            reverse('booking-list'),
            self._payload(other_offer, self.today + timedelta(days=2), self.today + timedelta(days=4)),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('offer', response.data)
