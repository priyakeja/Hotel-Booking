from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from content.models import (
    Amenity,
    ContactCard,
    ContactFaq,
    ContactMessage,
    ContactSettings,
    Feature,
    HeroBanner,
    NavLink,
    SiteSettings,
    Testimonial,
    TextSection,
)
from hotels.models import Hotel

User = get_user_model()


class SiteContentApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.settings_obj = SiteSettings.objects.create(
            site_title='SkyStay',
            tagline='Hotels & Resorts',
            footer_text='© 2025 SkyStay. All rights reserved.',
            contact_email='info@skystay.com',
            contact_phone='+91 98765 43210',
            address='123 Beach Road, Bali, Indonesia',
            logo_url='https://example.com/logo.png',
        )
        NavLink.objects.create(label='Home', url='/', location=NavLink.Location.HEADER, order=0)
        NavLink.objects.create(label='Hotels', url='/hotels', location=NavLink.Location.HEADER, order=1)
        NavLink.objects.create(label='Privacy Policy', url='/privacy', location=NavLink.Location.FOOTER_LEGAL)
        HeroBanner.objects.create(
            title='Discover Your Perfect Stay',
            eyebrow='Welcome to SkyStay',
            background_url='https://example.com/hero.jpg',
            is_active=True,
        )
        Feature.objects.create(title='Best Price Guarantee', icon='shield', description='Lowest prices.')
        Amenity.objects.create(name='Free WiFi', icon='wifi', show_on_homepage=True)
        Amenity.objects.create(name='Hidden Amenity', icon='x', show_on_homepage=False)
        Testimonial.objects.create(name='Sarah Johnson', message='Amazing experience!', rating=5)
        TextSection.objects.create(
            key=TextSection.Key.FEATURED_HOTELS, heading='Featured Hotels',
            subheading='Handpicked hotels', cta_text='View All Hotels', cta_link='/hotels',
        )
        cls.hotel = Hotel.objects.create(
            name='Grand Vista Resort', city='Bali', country='Indonesia',
            price_per_night='120.00', cover_image_url='https://example.com/hotel.jpg', is_featured=True,
        )

    def setUp(self):
        # SiteSettings.load() is memoised in the cache; start each test cold.
        cache.clear()

    def test_settings_endpoint_returns_branding_and_grouped_links(self):
        response = self.client.get(reverse('site-settings'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['site_title'], 'SkyStay')
        self.assertEqual(response.data['logo_display'], 'https://example.com/logo.png')
        self.assertEqual(response.data['contact_phone'], '+91 98765 43210')

        labels = [link['label'] for link in response.data['header_links']]
        self.assertEqual(labels, ['Home', 'Hotels'])
        self.assertEqual([link['label'] for link in response.data['legal_links']], ['Privacy Policy'])

    def test_home_payload_contains_every_dynamic_block(self):
        response = self.client.get(reverse('home-payload'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        for key in ('settings', 'heroes', 'features', 'featured_hotels', 'amenities', 'testimonials', 'sections', 'stats'):
            self.assertIn(key, response.data)

        self.assertEqual(response.data['heroes'][0]['title'], 'Discover Your Perfect Stay')
        self.assertEqual(response.data['featured_hotels'][0]['name'], 'Grand Vista Resort')
        self.assertEqual(response.data['stats']['hotels'], 1)

        # Only amenities flagged for the homepage are published.
        self.assertEqual([a['name'] for a in response.data['amenities']], ['Free WiFi'])

        # Text sections are keyed so the frontend can look them up by name.
        self.assertEqual(response.data['sections']['featured_hotels']['heading'], 'Featured Hotels')

    def test_amenity_homepage_filter(self):
        response = self.client.get(reverse('amenity-list'), {'homepage': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([a['name'] for a in response.data], ['Free WiFi'])

    def test_text_section_retrievable_by_key(self):
        response = self.client.get(f"/api/sections/{TextSection.Key.FEATURED_HOTELS}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['cta_link'], '/hotels')

    def test_site_settings_is_a_singleton(self):
        self.assertEqual(SiteSettings.load().pk, 1)
        self.assertEqual(SiteSettings.objects.count(), 1)

        # Saving another instance still writes to row 1 instead of adding a row.
        SiteSettings(site_title='Rebranded').save()
        self.assertEqual(SiteSettings.objects.count(), 1)
        self.assertEqual(SiteSettings.load().site_title, 'Rebranded')


class ContactPageApiTests(APITestCase):
    """The public Contact page is entirely database driven."""

    @classmethod
    def setUpTestData(cls):
        contact = ContactSettings.load()
        contact.page_title = 'Contact us'
        contact.intro_message = 'Reach out using the details below.'
        contact.response_time = 'Our team replies within one business day.'
        contact.email = 'info@skystay.com'
        contact.phone = '+91 98765 43210'
        contact.support_hours = '24/7'
        contact.property_name = 'SkyStay Bali'
        contact.address = '123 Beach Road'
        contact.city = 'Bali'
        contact.country = 'Indonesia'
        contact.latitude = '51.500000'
        contact.longitude = '-0.120000'
        contact.save()

        ContactCard.objects.create(
            kind=ContactCard.Kind.EMAIL, title='Email us',
            description='Reservations, changes and group bookings.', order=0,
        )
        ContactCard.objects.create(
            kind=ContactCard.Kind.LOCATION, title='Hotel Location', cta_label='View on Map',
            order=1,
        )
        ContactCard.objects.create(
            kind=ContactCard.Kind.PHONE, title='Hidden card', order=2, is_active=False,
        )
        ContactFaq.objects.create(question='Second?', answer='B', order=1)
        ContactFaq.objects.create(question='First?', answer='A', order=0)
        ContactFaq.objects.create(question='Draft?', answer='C', order=2, is_active=False)

    def setUp(self):
        cache.clear()

    def test_contact_payload_is_fully_dynamic(self):
        response = self.client.get(reverse('contact-page'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        settings_payload = response.data['settings']
        self.assertEqual(settings_payload['page_title'], 'Contact us')
        self.assertEqual(settings_payload['email'], 'info@skystay.com')
        self.assertEqual(settings_payload['phone'], '+91 98765 43210')
        self.assertEqual(settings_payload['support_hours'], '24/7')

        location = settings_payload['location']
        self.assertEqual(location['property_name'], 'SkyStay Bali')
        self.assertEqual(location['full_address'], '123 Beach Road, Bali, Indonesia')
        self.assertEqual(location['latitude'], 51.5)
        self.assertEqual(location['longitude'], -0.12)
        self.assertTrue(location['has_coordinates'])

        # Only active cards are published, in display order; the icon defaults
        # to the card kind so the admin never has to remember icon keywords.
        self.assertEqual([card['title'] for card in response.data['cards']], ['Email us', 'Hotel Location'])
        self.assertEqual(response.data['cards'][1]['icon'], 'map-pin')

        # FAQs follow display order and hide unpublished rows.
        self.assertEqual([faq['question'] for faq in response.data['faqs']], ['First?', 'Second?'])

    def test_location_follows_a_linked_property(self):
        hotel = Hotel.objects.create(
            name='Royal Palm Hotel', city='Dubai', country='UAE',
            address='Palm Jumeirah', price_per_night='150.00',
            latitude='25.112000', longitude='55.138000',
        )
        contact = ContactSettings.load()
        contact.location_hotel = hotel
        contact.save()

        location = self.client.get(reverse('contact-page')).data['settings']['location']
        self.assertEqual(location['property_name'], 'Royal Palm Hotel')
        self.assertEqual(location['full_address'], 'Palm Jumeirah, Dubai, UAE')
        self.assertEqual(location['latitude'], 25.112)
        self.assertEqual(location['longitude'], 55.138)

    def test_disabling_a_section_is_reported_to_the_frontend(self):
        contact = ContactSettings.load()
        contact.faq_enabled = False
        contact.map_enabled = False
        contact.contact_form_enabled = False
        contact.save()

        settings_payload = self.client.get(reverse('contact-page')).data['settings']
        self.assertFalse(settings_payload['faq_enabled'])
        self.assertFalse(settings_payload['map_enabled'])
        self.assertFalse(settings_payload['contact_form_enabled'])

    def test_phone_and_coordinates_are_validated(self):
        contact = ContactSettings(page_title='Contact us', phone='not-a-phone', latitude='12')
        with self.assertRaises(ValidationError) as ctx:
            contact.full_clean()
        self.assertIn('phone', ctx.exception.message_dict)
        self.assertIn('longitude', ctx.exception.message_dict)

        contact = ContactSettings(page_title='Contact us', latitude='91', longitude='10')
        with self.assertRaises(ValidationError):
            contact.full_clean()


class ContactFormApiTests(APITestCase):
    """Submitting the public contact form, and the admin's control over it."""

    def setUp(self):
        cache.clear()
        ContactSettings.objects.update_or_create(
            pk=1,
            defaults={'page_title': 'Contact us', 'contact_form_enabled': True},
        )

    def _post(self, payload):
        return self.client.post(reverse('contact-message-create'), payload, format='json')

    def test_message_is_stored_with_new_status(self):
        response = self._post({
            'name': 'Priya',
            'email': 'priya@example.com',
            'phone': '9876543210',
            'booking_reference': 'sky-7f3k9a',
            'subject': 'Late check-in',
            'message': 'We land at 22:00 — can the room be held?',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        message = ContactMessage.objects.get()
        self.assertEqual(message.status, ContactMessage.Status.NEW)
        self.assertEqual(message.booking_reference, 'SKY-7F3K9A')
        self.assertEqual(message.email, 'priya@example.com')

    def test_submitted_text_is_sanitised(self):
        self._post({
            'name': '<script>alert(1)</script>Sam',
            'email': 'sam@example.com',
            'phone': '9876543210',
            'subject': 'Hello <b>there</b>',
            'message': '<img src=x onerror=alert(1)>Need help',
        })
        message = ContactMessage.objects.get()
        self.assertNotIn('<', message.name)
        self.assertNotIn('<', message.subject)
        self.assertNotIn('<', message.message)
        self.assertIn('Need help', message.message)

    def test_required_fields_follow_the_admin_settings(self):
        # Subject is optional until the admin makes it required.
        ContactSettings.objects.filter(pk=1).update(form_subject_required=False)
        cache.clear()
        response = self._post({'name': 'Ann', 'email': 'a@example.com', 'phone': '9876543210', 'message': 'Hi'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        ContactSettings.objects.filter(pk=1).update(form_subject_required=True)
        cache.clear()
        response = self._post({'name': 'Ann', 'email': 'a@example.com', 'phone': '9876543210', 'message': 'Hi'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('subject', response.data)

    def test_booking_reference_field_can_be_switched_off(self):
        ContactSettings.objects.filter(pk=1).update(form_booking_reference_enabled=False)
        cache.clear()
        response = self._post({
            'name': 'Ann', 'email': 'a@example.com', 'phone': '9876543210',
            'subject': 'S', 'message': 'M', 'booking_reference': 'SHOULD-IGNORE',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContactMessage.objects.get().booking_reference, '')

    def test_email_is_validated(self):
        response = self._post({'name': 'A', 'email': 'nope', 'message': 'Hi'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_phone_is_mandatory_and_accepts_any_ten_digits(self):
        # Phone is required by default, so omitting it is a bad request.
        response = self._post({'name': 'Priya', 'email': 'p@example.com', 'subject': 'S', 'message': 'M'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

        # A plain 10-digit number is accepted, regardless of the leading digit.
        response = self._post({
            'name': 'Priya', 'email': 'p@example.com', 'phone': '1234567890',
            'subject': 'S', 'message': 'M',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(ContactMessage.objects.get().phone, '1234567890')

    def test_disabled_form_rejects_submissions(self):
        ContactSettings.objects.filter(pk=1).update(contact_form_enabled=False)
        cache.clear()
        response = self._post({'name': 'A', 'email': 'a@example.com', 'message': 'Hi'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(ContactMessage.objects.exists())

    def test_messages_are_never_exposed_on_a_public_endpoint(self):
        self._post({
            'name': 'Priya', 'email': 'priya@example.com',
            'subject': 'Secret subject', 'message': 'Secret message',
        })
        # The public payload carries only published settings, cards and FAQs —
        # the submitted enquiry itself must never come back out.
        payload = self.client.get(reverse('contact-page')).data
        self.assertEqual(set(payload), {'settings', 'cards', 'faqs'})
        self.assertNotIn('Secret subject', str(payload))
        self.assertNotIn('Secret message', str(payload))
        self.assertNotIn('priya@example.com', str(payload))


class AdminCmsRenderTests(APITestCase):
    """Every CMS screen in the admin must render for a staff user.

    The admin is the control panel for the whole site, so a broken form blocks all
    content editing. This covers a fallback image preview that passed a constant to
    ``format_html`` without interpolation args, which 500'd the Site Settings page
    whenever no logo image had been uploaded.
    """

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser(
            username='cmsadmin', email='cms@example.com', password='cms-pass-123'
        )
        # One row per content model so the change forms render with real data, and
        # deliberately without uploaded images to exercise the preview fallback.
        cls.settings_obj = SiteSettings.objects.create(site_title='SkyStay')
        cls.hotel = Hotel.objects.create(
            name='Grand Vista Resort', city='Bali', country='Indonesia', price_per_night='120.00'
        )
        # Contact rows so the contact admin screens (including the map picker form)
        # render with real data rather than an empty change form.
        cls.contact = ContactSettings.objects.create(
            page_title='Contact us', email='info@skystay.com', phone='+91 98765 43210',
            latitude='51.500000', longitude='-0.120000',
        )
        ContactCard.objects.create(kind=ContactCard.Kind.EMAIL, title='Email us')
        ContactFaq.objects.create(question='How do I modify my booking?', answer='From your dashboard.')
        ContactMessage.objects.create(
            name='Priya', email='priya@example.com', subject='Late check-in', message='Please hold the room.',
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.staff)

    def test_every_admin_screen_renders(self):
        for model, _model_admin in admin.site._registry.items():
            opts = model._meta
            with self.subTest(model=opts.label):
                changelist = reverse(f'admin:{opts.app_label}_{opts.model_name}_changelist')
                self.assertEqual(
                    self.client.get(changelist).status_code, 200, f'{opts.label} changelist'
                )

                obj = model.objects.first()
                if obj is None:
                    continue
                change = reverse(f'admin:{opts.app_label}_{opts.model_name}_change', args=[obj.pk])
                self.assertEqual(self.client.get(change).status_code, 200, f'{opts.label} change form')

    def test_admin_settings_edit_is_immediately_public(self):
        """Saving branding in the admin must be live on the API straight away."""
        response = self.client.post(
            reverse('admin:content_sitesettings_change', args=[self.settings_obj.pk]),
            {
                'site_title': 'Rebranded SkyStay',
                'tagline': 'Set from the CMS',
                'currency_code': 'USD',
                'currency_symbol': '$',
                'default_check_in_time': '14:00',
                'default_check_out_time': '11:00',
                'tax_percentage': '0.00',
                '_save': 'Save',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SiteSettings.load().site_title, 'Rebranded SkyStay')

        payload = self.client.get(reverse('site-settings')).data
        self.assertEqual(payload['site_title'], 'Rebranded SkyStay')

    def test_contact_settings_form_ships_the_map_picker(self):
        """The admin location screen must offer an interactive map, not just number boxes."""
        response = self.client.get(reverse('admin:content_contactsettings_change', args=[self.contact.pk]))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode()
        self.assertIn('skystay-location-map', html)
        self.assertIn('leaflet.js', html)
        self.assertIn('id_latitude', html)
        self.assertIn('id_longitude', html)
        self.assertIn('Search an address, city or hotel', html)

        # A hotel carries its own coordinates for the multi-property case.
        hotel_form = self.client.get(reverse('admin:hotels_hotel_change', args=[self.hotel.pk]))
        self.assertEqual(hotel_form.status_code, 200)
        self.assertIn('skystay-hotel-map', hotel_form.content.decode())

    def test_admin_map_uses_policy_compliant_osm_tiles(self):
        """The picker must follow the OSM tile policy, not get blocked with 403s.

        OSM requires the canonical host (no a/b/c subdomains) and a valid Referer,
        and Django's default ``Referrer-Policy: same-origin`` strips the Referer
        from these cross-origin requests.
        """
        # The Add Hotel screen is the one reported as showing blocked tiles.
        add_form = self.client.get(reverse('admin:hotels_hotel_add'))
        self.assertEqual(add_form.status_code, 200)
        html = add_form.content.decode()

        self.assertIn('https://tile.openstreetmap.org/{z}/{x}/{y}.png', html)
        self.assertNotIn('{s}.tile.openstreetmap.org', html)
        self.assertIn('referrerPolicy', html)
        self.assertIn('openstreetmap.org/copyright', html)
        self.assertIn('openstreetmap.org/fixthemap', html)

        # The response must let the browser send a Referer to OSM/Nominatim.
        self.assertEqual(add_form['Referrer-Policy'], 'strict-origin-when-cross-origin')

    def test_contact_message_inbox_lists_and_triages(self):
        """Staff see submissions, the public cannot, and status is editable inline."""
        changelist = reverse('admin:content_contactmessage_changelist')
        response = self.client.get(changelist)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Late check-in')
        self.assertContains(response, 'priya@example.com')
        self.assertContains(response, 'field-status')  # inline status editor

        message = ContactMessage.objects.get()
        self.assertNotIn(ContactMessage.Status.RESOLVED, [message.status])
        self.client.post(
            changelist,
            {
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '1',
                'form-MIN_NUM_FORMS': '0',
                'form-MAX_NUM_FORMS': '1000',
                'form-0-id': str(message.pk),
                'form-0-status': ContactMessage.Status.RESOLVED,
                '_save': 'Save',
            },
        )
        message.refresh_from_db()
        self.assertEqual(message.status, ContactMessage.Status.RESOLVED)

        # A signed-out visitor is bounced to the admin login, never the inbox.
        self.client.logout()
        redirected = self.client.get(changelist)
        self.assertEqual(redirected.status_code, 302)
        self.assertIn('/admin/login/', redirected['Location'])

    def test_admin_contact_edit_is_immediately_public(self):
        """Editing the Contact page in the admin must be live on the API at once."""
        response = self.client.post(
            reverse('admin:content_contactsettings_change', args=[self.contact.pk]),
            {
                'page_title': 'Contact us',
                'intro_message': 'Reach out any time.',
                'response_time': 'We reply within a day.',
                'email': 'reservations@skystay.com',
                'phone': '+91 98765 99999',
                'support_hours': '24/7',
                'property_name': 'SkyStay',
                'address': '123 Beach Road',
                'city': 'Bali',
                'country': 'Indonesia',
                'latitude': '-8.409500',
                'longitude': '115.188900',
                'primary_cta_text': 'Browse hotels',
                'primary_cta_link': '/hotels',
                'secondary_cta_text': 'Contact Support',
                'secondary_cta_link': '/dashboard/bookings',
                'booking_support_title': 'Need help with a booking?',
                'booking_support_button_text': 'Manage my booking',
                'booking_support_button_link': '/dashboard/bookings',
                'support_title': 'Guest support',
                'form_success_message': 'Thanks!',
                'form_error_message': 'Something went wrong.',
                'seo_title': 'Contact SkyStay Hotels & Resorts',
                'cards_enabled': 'on',
                'map_enabled': 'on',
                'contact_form_enabled': 'on',
                'faq_enabled': 'on',
                'intro_enabled': 'on',
                'booking_support_enabled': 'on',
                'support_enabled': 'on',
                'form_name_required': 'on',
                'form_email_required': 'on',
                'form_booking_reference_enabled': 'on',
                'form_subject_required': 'on',
                'form_message_required': 'on',
                '_save': 'Save',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactSettings.load().phone, '+91 98765 99999')

        payload = self.client.get(reverse('contact-page')).data['settings']
        self.assertEqual(payload['phone'], '+91 98765 99999')
        self.assertEqual(payload['email'], 'reservations@skystay.com')
