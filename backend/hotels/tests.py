from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from bookings.models import Booking
from content.models import Amenity
from hotels.models import Hotel, Room

User = get_user_model()


class HotelApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.wifi = Amenity.objects.create(name='Free WiFi', icon='wifi')
        cls.pool = Amenity.objects.create(name='Swimming Pool', icon='pool')

        cls.grand = Hotel.objects.create(
            name='Grand Vista Resort', city='Bali', country='Indonesia',
            price_per_night='120.00', star_rating='5.0', is_featured=True,
            cover_image_url='https://example.com/g.jpg', highlights='Beachfront Location\nInfinity Pool',
        )
        cls.grand.amenities.set([cls.wifi, cls.pool])
        cls.grand_room = Room.objects.create(
            hotel=cls.grand, name='Deluxe Room', room_type=Room.RoomType.DELUXE,
            price_per_night='120.00', capacity=2, max_guests=3, bed_type='1 King Bed',
            total_rooms=2, cover_image_url='https://example.com/r.jpg',
        )
        cls.grand_room.amenity_list.set([cls.wifi])

        cls.ocean = Hotel.objects.create(
            name='Ocean Breeze Resort', city='Goa', country='India',
            price_per_night='90.00', star_rating='3.0',
        )
        Room.objects.create(
            hotel=cls.ocean, name='Standard Room', room_type=Room.RoomType.STANDARD,
            price_per_night='90.00', capacity=2, max_guests=2, total_rooms=5,
        )

        cls.user = User.objects.create_user(username='guest', email='guest@example.com', password='pass-1234')

    # -- listing ---------------------------------------------------------
    def test_list_is_paginated_and_includes_rating_metadata(self):
        response = self.client.get(reverse('hotel-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 2)

        grand = next(h for h in response.data['results'] if h['name'] == 'Grand Vista Resort')
        self.assertEqual(grand['location'], 'Bali, Indonesia')
        self.assertEqual(grand['room_count'], 1)
        self.assertEqual(str(grand['starting_price']), '120.00')

    def test_pagination_envelope_reports_page_count(self):
        """The frontend relies on `num_pages` to decide whether to show paging controls."""
        for index in range(12):
            Hotel.objects.create(
                name=f'Filler Hotel {index}', city='Lisbon', country='Portugal',
                price_per_night='75.00',
            )

        first = self.client.get(reverse('hotel-list'))
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['count'], 14)
        self.assertEqual(first.data['page_size'], 9)
        self.assertEqual(first.data['num_pages'], 2)
        self.assertEqual(first.data['current_page'], 1)
        self.assertEqual(len(first.data['results']), 9)
        self.assertIsNotNone(first.data['next'])
        self.assertIsNone(first.data['previous'])

        second = self.client.get(reverse('hotel-list'), {'page': 2})
        self.assertEqual(second.data['current_page'], 2)
        self.assertEqual(len(second.data['results']), 5)
        self.assertIsNone(second.data['next'])
        self.assertIsNotNone(second.data['previous'])

        # Page 2 must not repeat page 1's rows.
        first_ids = {h['id'] for h in first.data['results']}
        second_ids = {h['id'] for h in second.data['results']}
        self.assertFalse(first_ids & second_ids)

    def test_page_size_can_be_overridden_by_the_client(self):
        for index in range(4):
            Hotel.objects.create(
                name=f'Filler Hotel {index}', city='Lisbon', country='Portugal', price_per_night='75.00'
            )
        response = self.client.get(reverse('hotel-list'), {'page_size': 3})
        self.assertEqual(len(response.data['results']), 3)
        self.assertEqual(response.data['num_pages'], 2)
        self.assertEqual(response.data['page_size'], 3)

    def test_search_filter_matches_city_and_name(self):
        response = self.client.get(reverse('hotel-list'), {'search': 'goa'})
        self.assertEqual([h['name'] for h in response.data['results']], ['Ocean Breeze Resort'])

    def test_price_range_filter(self):
        response = self.client.get(reverse('hotel-list'), {'min_price': '100', 'max_price': '130'})
        self.assertEqual([h['name'] for h in response.data['results']], ['Grand Vista Resort'])

    def test_star_rating_filter(self):
        response = self.client.get(reverse('hotel-list'), {'star_rating': '5'})
        self.assertEqual([h['name'] for h in response.data['results']], ['Grand Vista Resort'])

    def test_amenity_filter_requires_every_amenity(self):
        response = self.client.get(reverse('hotel-list'), {'amenity': ['Free WiFi', 'Swimming Pool']})
        self.assertEqual([h['name'] for h in response.data['results']], ['Grand Vista Resort'])

    def test_guest_capacity_filter_excludes_small_rooms(self):
        response = self.client.get(reverse('hotel-list'), {'guests': '3'})
        self.assertEqual([h['name'] for h in response.data['results']], ['Grand Vista Resort'])

    def test_ordering_by_price(self):
        response = self.client.get(reverse('hotel-list'), {'sort': 'price_low'})
        self.assertEqual(
            [h['name'] for h in response.data['results']],
            ['Ocean Breeze Resort', 'Grand Vista Resort'],
        )

    # -- detail ----------------------------------------------------------
    def test_detail_lookup_by_slug_returns_rooms_and_highlights(self):
        response = self.client.get(f'/api/hotels/{self.grand.slug}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'grand-vista-resort-bali')
        self.assertEqual(response.data['highlights'], ['Beachfront Location', 'Infinity Pool'])
        self.assertEqual(len(response.data['rooms']), 1)
        self.assertEqual(response.data['rooms'][0]['amenities'][0]['name'], 'Free WiFi')

    def test_filters_endpoint_returns_sidebar_metadata(self):
        response = self.client.get(reverse('hotel-filters'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['locations']), 2)
        self.assertEqual(str(response.data['price_range']['min']), '90.00')
        self.assertEqual(str(response.data['price_range']['max']), '120.00')
        self.assertEqual(len(response.data['room_types']), 5)

    # -- availability ----------------------------------------------------
    def test_availability_reflects_inventory(self):
        check_in = self.today + timedelta(days=10)
        check_out = check_in + timedelta(days=2)

        response = self.client.get(
            reverse('room-availability', args=[self.grand_room.id]),
            {'check_in': check_in.isoformat(), 'check_out': check_out.isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_available'])
        self.assertEqual(response.data['rooms_left'], 2)
        self.assertEqual(response.data['nights'], 2)
        # 2 nights x $120 with 0% tax configured by default.
        self.assertEqual(response.data['total_price'], '240.00')

    def test_availability_exhausted_when_all_rooms_booked(self):
        check_in = self.today + timedelta(days=10)
        check_out = check_in + timedelta(days=2)
        for _ in range(2):
            Booking.objects.create(
                user=self.user, room=self.grand_room, check_in=check_in, check_out=check_out,
                guests=1, guest_name='G', guest_email='g@example.com',
                status=Booking.Status.CONFIRMED,
            )

        response = self.client.get(
            reverse('room-availability', args=[self.grand_room.id]),
            {'check_in': check_in.isoformat(), 'check_out': check_out.isoformat()},
        )
        self.assertFalse(response.data['is_available'])
        self.assertEqual(response.data['rooms_left'], 0)

    def test_availability_requires_valid_dates(self):
        bad = self.client.get(reverse('room-availability', args=[self.grand_room.id]), {'check_in': 'nope'})
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hotel_availability_action_lists_rooms(self):
        check_in = self.today + timedelta(days=5)
        response = self.client.get(
            reverse('hotel-availability', args=[self.grand.slug]),
            {'check_in': check_in.isoformat(), 'check_out': (check_in + timedelta(days=1)).isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['rooms'][0]['name'], 'Deluxe Room')

    def test_cross_hotel_availability_search_respects_guest_count(self):
        check_in = self.today + timedelta(days=5)
        response = self.client.get(
            reverse('availability-search-list'),
            {
                'check_in': check_in.isoformat(),
                'check_out': (check_in + timedelta(days=2)).isoformat(),
                'guests': 3,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row['hotel']['name'] for row in response.data['results']], ['Grand Vista Resort'])

    def test_listing_excludes_hotels_with_no_inventory_for_the_dates(self):
        """A hotel that is fully booked is filtered out and the empty state explains why."""
        check_in = self.today + timedelta(days=5)
        check_out = check_in + timedelta(days=1)
        for _ in range(2):
            Booking.objects.create(
                user=self.user, room=self.grand_room, check_in=check_in, check_out=check_out,
                guests=1, guest_name='G', guest_email='g@example.com',
                status=Booking.Status.CONFIRMED,
            )
        response = self.client.get(
            reverse('hotel-list'),
            {'check_in': check_in.isoformat(), 'check_out': check_out.isoformat(), 'search': 'Grand'},
        )
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['meta']['empty_reason'], 'availability')

    def test_listing_without_dates_still_reports_a_sold_out_hotel(self):
        """Without dates there is nothing to check, so the hotel stays in the list."""
        response = self.client.get(reverse('hotel-list'), {'search': 'Grand'})
        self.assertEqual(response.data['count'], 1)
        self.assertTrue(response.data['results'][0]['is_available'])


class HotelSearchRegressionTests(APITestCase):
    """Regression coverage for the tolerant, correctly-ordered search pipeline."""

    @classmethod
    def setUpTestData(cls):
        cls.bangalore = Hotel.objects.create(
            name='City Central Hotel', city='Bangalore', state='Karnataka', country='India',
            price_per_night='80.00', star_rating='4.0', is_featured=False,
            short_description='Business-ready hotel in the heart of the city.',
        )
        Room.objects.create(
            hotel=cls.bangalore, name='Smart Room', room_type=Room.RoomType.STANDARD,
            price_per_night='80.00', capacity=2, max_guests=2, total_rooms=12,
        )
        Room.objects.create(
            hotel=cls.bangalore, name='Business Suite', room_type=Room.RoomType.PREMIUM,
            price_per_night='125.00', capacity=2, max_guests=3, total_rooms=5,
        )

        cls.bali = Hotel.objects.create(
            name='Grand Vista Resort', city='Bali', country='Indonesia',
            price_per_night='120.00', star_rating='5.0', is_featured=True,
        )
        Room.objects.create(
            hotel=cls.bali, name='Deluxe Room', room_type=Room.RoomType.DELUXE,
            price_per_night='120.00', capacity=2, max_guests=3, total_rooms=2,
        )

        cls.user = User.objects.create_user(
            username='searcher', email='searcher@example.com', password='pass-1234',
            city='Goa', country='India',
        )

    def names_for(self, **params):
        response = self.client.get(reverse('hotel-list'), params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return [hotel['name'] for hotel in response.data['results']]

    # -- tolerant location search ----------------------------------------
    def test_search_variants_all_resolve_to_bangalore(self):
        for term in ('Bangalore', 'bangalore', 'BANGALORE', '  Bangalore  ', 'banglore', 'Banglore'):
            self.assertEqual(self.names_for(search=term), ['City Central Hotel'], term)

    def test_search_matches_state_country_and_name(self):
        self.assertEqual(self.names_for(search='Karnataka'), ['City Central Hotel'])
        self.assertEqual(self.names_for(search='India'), ['City Central Hotel'])
        self.assertEqual(self.names_for(search='city central'), ['City Central Hotel'])

    def test_search_does_not_require_an_exact_match(self):
        self.assertIn('City Central Hotel', self.names_for(search='Bangalore India'))
        self.assertEqual(self.names_for(search='atlantis'), [])

    # -- featured is intentional only ------------------------------------
    def test_normal_listing_does_not_filter_by_featured(self):
        names = self.names_for()
        self.assertIn('City Central Hotel', names)
        self.assertIn('Grand Vista Resort', names)

    def test_featured_filter_is_applied_only_when_requested(self):
        self.assertEqual(self.names_for(featured='true'), ['Grand Vista Resort'])

    # -- date availability -----------------------------------------------
    def test_hotel_with_inventory_for_the_dates_is_returned(self):
        check_in = timezone.localdate() + timedelta(days=30)
        self.assertEqual(
            self.names_for(
                search='banglore',
                check_in=check_in.isoformat(),
                check_out=(check_in + timedelta(days=1)).isoformat(),
                guests='2',
            ),
            ['City Central Hotel'],
        )

    def test_hotel_without_inventory_is_excluded_with_reason(self):
        check_in = timezone.localdate() + timedelta(days=30)
        for _ in range(2):
            Booking.objects.create(
                user=self.user, room=self.bali.rooms.first(), check_in=check_in,
                check_out=check_in + timedelta(days=1), guests=1, guest_name='G',
                guest_email='g@example.com', status=Booking.Status.CONFIRMED,
            )
        response = self.client.get(
            reverse('hotel-list'),
            {
                'search': 'Bali',
                'check_in': check_in.isoformat(),
                'check_out': (check_in + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['meta']['empty_reason'], 'availability')

    # -- guest capacity --------------------------------------------------
    def test_two_guests_fit_a_two_guest_room(self):
        self.assertEqual(self.names_for(search='Bangalore', guests='2'), ['City Central Hotel'])

    def test_too_many_guests_is_reported_as_a_capacity_problem(self):
        # Bali has one room type sleeping 3 with two rooms (max 6 guests).
        check_in = timezone.localdate() + timedelta(days=30)
        response = self.client.get(
            reverse('hotel-list'),
            {
                'search': 'Bali',
                'check_in': check_in.isoformat(),
                'check_out': (check_in + timedelta(days=1)).isoformat(),
                'guests': '8',
            },
        )
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['meta']['empty_reason'], 'capacity')

    # -- empty-state diagnostics -----------------------------------------
    def test_unknown_destination_reports_a_location_problem(self):
        response = self.client.get(reverse('hotel-list'), {'search': 'atlantis'})
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['meta']['empty_reason'], 'location')

    # -- the signed-in profile must not change the search ----------------
    def test_profile_city_does_not_restrict_the_search(self):
        anonymous = self.names_for(search='banglore')
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.names_for(search='banglore'), anonymous)
        self.assertEqual(self.names_for(search='banglore'), ['City Central Hotel'])
