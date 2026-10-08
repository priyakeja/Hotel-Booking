from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

User = get_user_model()


class AuthApiTests(APITestCase):
    def test_register_creates_user_without_signing_them_in(self):
        response = self.client.post(
            reverse('auth-register'),
            {
                'username': 'newguest',
                'email': 'NewGuest@Example.com',
                'first_name': 'New',
                'last_name': 'Guest',
                'phone': '9876543210',
                'city': 'Chennai',
                'country': 'India',
                'address': 'Anna Nagar',
                'password': 'Str0ng!Pass',
                'password_confirm': 'Str0ng!Pass',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # No auth token is handed out: the customer must sign in separately.
        self.assertNotIn('token', response.data)
        self.assertFalse(Token.objects.filter(user__username='newguest').exists())
        self.assertEqual(response.data['user']['email'], 'newguest@example.com')
        self.assertEqual(response.data['user']['role'], User.Role.CUSTOMER)

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            reverse('auth-register'),
            {
                'username': 'mismatch',
                'email': 'mismatch@example.com',
                'first_name': 'Valid',
                'last_name': 'User',
                'phone': '9876543210',
                'city': 'Chennai',
                'country': 'India',
                'address': 'Anna Nagar',
                'password': 'Str0ng!Pass',
                'password_confirm': 'Other!Pass1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def _valid_payload(self, **overrides):
        payload = {
            'username': 'validuser',
            'email': 'valid@example.com',
            'first_name': 'Valid',
            'last_name': 'User',
            'phone': '9876543210',
            'city': 'Chennai',
            'country': 'India',
            'address': 'Anna Nagar',
            'password': 'Str0ng!Pass',
            'password_confirm': 'Str0ng!Pass',
        }
        payload.update(overrides)
        return payload

    def test_register_rejects_short_name(self):
        response = self.client.post(
            reverse('auth-register'), self._valid_payload(first_name='Al'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('first_name', response.data)

    def test_register_accepts_single_character_last_name(self):
        response = self.client.post(
            reverse('auth-register'), self._valid_payload(last_name='P'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['user']['last_name'], 'P')

    def test_register_accepts_any_ten_digit_mobile(self):
        # Not restricted to the 6-9 prefix any more — a plain 10-digit number is valid.
        response = self.client.post(
            reverse('auth-register'), self._valid_payload(phone='1234567890'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['user']['phone'], '1234567890')

    def test_register_saves_and_returns_profile_details(self):
        response = self.client.post(reverse('auth-register'), self._valid_payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

        user = User.objects.get(username='validuser')
        self.assertEqual((user.city, user.country, user.address), ('Chennai', 'India', 'Anna Nagar'))
        # The dashboard reads the profile straight off this payload.
        self.assertEqual(response.data['user']['city'], 'Chennai')
        self.assertEqual(response.data['user']['country'], 'India')
        self.assertEqual(response.data['user']['address'], 'Anna Nagar')

    def test_register_requires_city_country_and_address(self):
        for field in ('city', 'country', 'address'):
            response = self.client.post(
                reverse('auth-register'), self._valid_payload(**{field: ''}), format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(field, response.data)

    def test_register_requires_mobile_number(self):
        response = self.client.post(
            reverse('auth-register'), self._valid_payload(phone=''), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_register_rejects_non_mobile_number(self):
        response = self.client.post(
            reverse('auth-register'), self._valid_payload(phone='12345'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_register_normalises_mobile_digits(self):
        response = self.client.post(
            reverse('auth-register'), self._valid_payload(phone='+91 98765 43210'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['user']['phone'], '9876543210')

    def test_register_rejects_weak_password(self):
        # Passes Django's own validators but lacks an uppercase letter / digit / symbol.
        response = self.client.post(
            reverse('auth-register'),
            self._valid_payload(password='onlylowerletters', password_confirm='onlylowerletters'),
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('uppercase', str(response.data).lower())

    def test_login_accepts_email_as_username(self):
        user = User.objects.create_user(
            username='sarah', email='sarah@example.com', password='secret-pass-1'
        )
        response = self.client.post(
            reverse('auth-login'),
            {'username': 'sarah@example.com', 'password': 'secret-pass-1'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['id'], user.id)

    def test_login_rejects_bad_credentials(self):
        User.objects.create_user(username='sarah', email='sarah@example.com', password='secret-pass-1')
        response = self.client.post(
            reverse('auth-login'), {'username': 'sarah', 'password': 'wrong'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_handles_legacy_user_without_profile_fields(self):
        # Accounts created before the profile fields existed must still load,
        # with empty values rather than an error.
        user = User.objects.create_user(
            username='legacy', email='legacy@example.com', password='secret-pass-1'
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['city'], '')
        self.assertEqual(response.data['country'], '')
        self.assertEqual(response.data['address'], '')

    def test_me_returns_profile_and_patch_updates_it(self):
        user = User.objects.create_user(username='sarah', email='sarah@example.com', password='secret-pass-1')
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(reverse('auth-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'sarah')

        response = self.client.patch(reverse('auth-me'), {'phone': '+1 555 0101'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.phone, '+1 555 0101')

    def test_logout_revokes_token(self):
        user = User.objects.create_user(username='sarah', email='sarah@example.com', password='secret-pass-1')
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        self.assertEqual(self.client.post(reverse('auth-logout')).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(user=user).exists())
