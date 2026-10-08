from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from hotels.models import Hotel
from reviews.models import Review

User = get_user_model()


class ReviewApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hotel = Hotel.objects.create(
            name='Grand Vista Resort', city='Bali', country='Indonesia', price_per_night='120.00',
        )
        cls.other_hotel = Hotel.objects.create(
            name='Ocean Breeze Resort', city='Goa', country='India', price_per_night='90.00',
        )
        cls.user = User.objects.create_user(username='guest', email='guest@example.com', password='pass-1234')
        cls.other = User.objects.create_user(username='other', email='other@example.com', password='pass-1234')

    def setUp(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_public_listing_shows_only_approved_reviews(self):
        Review.objects.create(hotel=self.hotel, user=self.user, rating=5, comment='Great')
        Review.objects.create(hotel=self.hotel, user=self.other, rating=1, comment='Hidden', is_approved=False)

        response = self.client.get(reverse('review-list'), {'hotel': self.hotel.slug})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['comment'], 'Great')

    def test_listing_filtered_by_hotel_slug(self):
        Review.objects.create(hotel=self.hotel, user=self.user, rating=5, comment='Great')
        Review.objects.create(hotel=self.other_hotel, user=self.other, rating=4, comment='Nice')

        response = self.client.get(reverse('review-list'), {'hotel': self.other_hotel.slug})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['comment'], 'Nice')

    def test_creating_review_updates_hotel_rating_aggregate(self):
        self.client.post(
            reverse('review-list'),
            {'hotel': self.hotel.id, 'rating': 5, 'title': 'Dreamy', 'comment': 'Loved it'},
            format='json',
        )
        self.client.post(
            reverse('review-list'),
            {'hotel': self.hotel.id, 'rating': 3, 'comment': 'It was fine'},
            format='json',
        )

        self.hotel.refresh_from_db()
        self.assertEqual(self.hotel.review_count, 2)
        self.assertEqual(float(self.hotel.rating_average), 4.0)

        response = self.client.get(f'/api/hotels/{self.hotel.slug}/')
        self.assertEqual(response.data['review_count'], 2)
        self.assertEqual(float(response.data['rating']), 4.0)

    def test_review_requires_authentication(self):
        self.client.credentials()
        response = self.client.post(
            reverse('review-list'), {'hotel': self.hotel.id, 'rating': 5, 'comment': 'x'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rating_out_of_range_is_rejected(self):
        response = self.client.post(
            reverse('review-list'), {'hotel': self.hotel.id, 'rating': 9, 'comment': 'x'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', response.data)

    def test_author_can_delete_own_review_and_aggregate_is_recomputed(self):
        created = self.client.post(
            reverse('review-list'), {'hotel': self.hotel.id, 'rating': 4, 'comment': 'Good'}, format='json'
        )
        self.hotel.refresh_from_db()
        self.assertEqual(self.hotel.review_count, 1)

        response = self.client.delete(reverse('review-detail', args=[created.data['id']]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.hotel.refresh_from_db()
        self.assertEqual(self.hotel.review_count, 0)
        self.assertEqual(float(self.hotel.rating_average), 0.0)

    def test_cannot_delete_another_users_review(self):
        review = Review.objects.create(hotel=self.hotel, user=self.other, rating=3, comment='Mine')
        response = self.client.delete(reverse('review-detail', args=[review.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hidden_review_is_excluded_from_the_rating(self):
        review = Review.objects.create(hotel=self.hotel, user=self.user, rating=5, comment='Great')
        self.hotel.refresh_from_db()
        self.assertEqual(float(self.hotel.rating_average), 5.0)

        review.is_approved = False
        review.save()
        self.hotel.refresh_from_db()
        self.assertEqual(self.hotel.review_count, 0)
