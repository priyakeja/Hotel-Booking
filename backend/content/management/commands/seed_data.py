"""Seed the database with the dynamic demo content used by the frontend.

Safe to run repeatedly: every record is matched on a natural key and updated
instead of duplicated. Use ``--flush`` to delete existing demo content first.

    python manage.py seed_data
    python manage.py seed_data --flush
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from content.models import (
    Amenity,
    ContactCard,
    ContactFaq,
    ContactSettings,
    Feature,
    GalleryImage,
    HeroBanner,
    NavLink,
    SiteSettings,
    Testimonial,
    TextSection,
)
from hotels.models import Hotel, HotelImage, Room, RoomImage
from reviews.models import Review

User = get_user_model()

# External imagery so the demo works without shipping binary assets. Every URL
# below is verified reachable; uploads through the admin always take priority.
IMG = {
    'hero_bali': 'https://images.unsplash.com/photo-1582719508461-905c673771fd?auto=format&fit=crop&w=1920&q=80',
    'hero_pool': 'https://images.unsplash.com/photo-1540541338287-41700207dee6?auto=format&fit=crop&w=1920&q=80',
    'grand_vista': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80',
    'grand_vista_2': 'https://images.unsplash.com/photo-1571003123894-1f0594d2b5d9?auto=format&fit=crop&w=1200&q=80',
    'grand_vista_3': 'https://images.unsplash.com/photo-1584132967334-10e028bd69f7?auto=format&fit=crop&w=1200&q=80',
    'royal_palm': 'https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?auto=format&fit=crop&w=1200&q=80',
    'royal_palm_2': 'https://images.unsplash.com/photo-1578683010236-d716f9a3f461?auto=format&fit=crop&w=1200&q=80',
    'royal_palm_3': 'https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1200&q=80',
    'ocean_breeze': 'https://images.unsplash.com/photo-1615880484746-a134be9a6ecf?auto=format&fit=crop&w=1200&q=80',
    'ocean_breeze_2': 'https://images.unsplash.com/photo-1595576508898-0ad5c879a061?auto=format&fit=crop&w=1200&q=80',
    'ocean_breeze_3': 'https://images.unsplash.com/photo-1571896349842-33c89424de2d?auto=format&fit=crop&w=1200&q=80',
    'mountain_view': 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80',
    'mountain_view_2': 'https://images.unsplash.com/photo-1564501049412-61c2a3083791?auto=format&fit=crop&w=1200&q=80',
    'mountain_view_3': 'https://images.unsplash.com/photo-1596436889106-be35e843f974?auto=format&fit=crop&w=1200&q=80',
    'lake_view': 'https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&q=80',
    'lake_view_2': 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=1200&q=80',
    'lake_view_3': 'https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?auto=format&fit=crop&w=1200&q=80',
    'city_central': 'https://images.unsplash.com/photo-1512918728675-ed5a9ecdebfd?auto=format&fit=crop&w=1200&q=80',
    'city_central_2': 'https://images.unsplash.com/photo-1445019980597-93fa8acb246c?auto=format&fit=crop&w=1200&q=80',
    'city_central_3': 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1200&q=80',
    'room_king': 'https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80',
    'room_deluxe': 'https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&q=80',
    'room_premium': 'https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1200&q=80',
    'room_suite': 'https://images.unsplash.com/photo-1564501049412-61c2a3083791?auto=format&fit=crop&w=1200&q=80',
    'room_bath': 'https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?auto=format&fit=crop&w=1200&q=80',
    'room_balcony': 'https://images.unsplash.com/photo-1618773928121-c32242e63f39?auto=format&fit=crop&w=1200&q=80',
    'spa': 'https://images.unsplash.com/photo-1496417263034-38ec4f0b665a?auto=format&fit=crop&w=1200&q=80',
    'restaurant': 'https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=1200&q=80',
    'avatar_sarah': 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=200&q=80',
    'avatar_michael': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=200&q=80',
    'avatar_priya': 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=200&q=80',
    'avatar_delyanka': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=200&q=80',
}

AMENITIES = [
    ('Free WiFi', 'wifi', 'High speed Wi-Fi in every room and public area.'),
    ('Swimming Pool', 'pool', 'Outdoor pool with sun loungers and poolside service.'),
    ('Restaurant', 'restaurant', 'All-day dining with local and international cuisine.'),
    ('Spa & Wellness', 'spa', 'Signature treatments, sauna and steam rooms.'),
    ('Room Service', 'room-service', '24/7 in-room dining.'),
    ('Parking', 'parking', 'Complimentary on-site parking for guests.'),
]

FEATURES = [
    ('Best Price Guarantee', 'shield', 'Get the lowest prices for your stays.'),
    ('24/7 Support', 'clock', 'We are here to help, any time of day.'),
    ('Secure Booking', 'lock', 'Your data is safe with us.'),
    ('Exclusive Offers', 'tag', 'Special deals & discounts for members.'),
]

HOTELS = [
    {
        'name': 'Grand Vista Resort',
        'city': 'Bali',
        'country': 'Indonesia',
        'address': '123 Beach Road, Bali, Indonesia',
        'star_rating': Decimal('5.0'),
        'price_per_night': Decimal('120.00'),
        'is_featured': True,
        'short_description': 'Oceanfront resort with infinity pool and world-class spa.',
        'description': (
            'Grand Vista Resort offers a perfect blend of luxury and comfort with stunning ocean '
            'views, world-class amenities and exceptional service. Experience the best of Bali with '
            'our premium accommodations, fine dining and relaxing spa facilities.'
        ),
        'highlights': [
            'Beachfront Location',
            'Luxurious Rooms',
            'Infinity Pool',
            'Fine Breakfast',
            'Fine dining and relaxing spa facilities.',
        ],
        'amenities': ['Free WiFi', 'Swimming Pool', 'Restaurant', 'Spa & Wellness', 'Parking'],
        'images': ['grand_vista', 'grand_vista_2', 'grand_vista_3', 'spa'],
        'rooms': [
            ('Deluxe Room', 'deluxe', Decimal('120.00'), 2, 3, '1 King Bed', 1, 28, 8, 'room_deluxe'),
            ('Premium Room', 'premium', Decimal('160.00'), 3, 4, '2 Queen Beds', 2, 42, 5, 'room_premium'),
            ('Ocean Suite', 'suite', Decimal('240.00'), 4, 5, '1 King Bed + Sofa', 2, 65, 3, 'room_suite'),
        ],
    },
    {
        'name': 'Royal Palm Hotel',
        'city': 'Dubai',
        'country': 'UAE',
        'address': 'Palm Jumeirah, Dubai, UAE',
        'star_rating': Decimal('5.0'),
        'price_per_night': Decimal('150.00'),
        'is_featured': True,
        'short_description': 'Skyline views, rooftop pool and a private beach club.',
        'description': (
            'Royal Palm Hotel pairs contemporary Arabian design with effortless service. Every room '
            'looks out over the marina, and the rooftop pool is open until late.'
        ),
        'highlights': ['Rooftop Infinity Pool', 'Private Beach Club', 'Airport Transfers', 'Business Lounge'],
        'amenities': ['Free WiFi', 'Swimming Pool', 'Restaurant', 'Room Service', 'Parking'],
        'images': ['royal_palm', 'royal_palm_2', 'royal_palm_3', 'restaurant'],
        'rooms': [
            ('Deluxe Room', 'deluxe', Decimal('150.00'), 2, 3, '1 King Bed', 1, 32, 6, 'room_king'),
            ('Executive Suite', 'suite', Decimal('210.00'), 3, 4, '1 King Bed + Lounge', 2, 55, 4, 'room_suite'),
        ],
    },
    {
        'name': 'Ocean Breeze Resort',
        'city': 'Goa',
        'country': 'India',
        'address': 'Candolim Beach Road, Goa, India',
        'star_rating': Decimal('4.0'),
        'price_per_night': Decimal('90.00'),
        'is_featured': True,
        'short_description': 'Laid-back beach resort steps from the sand.',
        'description': (
            'Ocean Breeze Resort is a relaxed beachfront escape with palm-shaded gardens, an outdoor '
            'pool and a beach bar that stays open for sunset.'
        ),
        'highlights': ['Direct Beach Access', 'Garden Cottages', 'Water Sports Desk', 'Beach Bar'],
        'amenities': ['Free WiFi', 'Swimming Pool', 'Restaurant', 'Parking'],
        'images': ['ocean_breeze', 'ocean_breeze_2', 'ocean_breeze_3'],
        'rooms': [
            ('Standard Room', 'standard', Decimal('90.00'), 2, 2, '2 Single Beds', 2, 22, 10, 'room_bath'),
            ('Deluxe Room', 'deluxe', Decimal('120.00'), 3, 3, '1 King Bed', 1, 30, 6, 'room_deluxe'),
        ],
    },
    {
        'name': 'Mountain View Hotel',
        'city': 'Manali',
        'country': 'India',
        'address': 'Old Manali Road, Manali, India',
        'star_rating': Decimal('4.0'),
        'price_per_night': Decimal('110.00'),
        'is_featured': True,
        'short_description': 'Alpine retreat with valley-facing balconies.',
        'description': (
            'Wake up to pine forests and snow-capped peaks. Mountain View Hotel has a fireplace lounge, '
            'a heated indoor pool and guided treks from the doorstep.'
        ),
        'highlights': ['Valley View Balconies', 'Fireplace Lounge', 'Guided Treks', 'Heated Indoor Pool'],
        'amenities': ['Free WiFi', 'Restaurant', 'Room Service', 'Parking'],
        'images': ['mountain_view', 'mountain_view_2', 'mountain_view_3'],
        'rooms': [
            ('Deluxe Valley Room', 'deluxe', Decimal('110.00'), 2, 3, '1 Queen Bed', 1, 26, 8, 'room_balcony'),
            ('Family Suite', 'suite', Decimal('170.00'), 4, 5, '1 King + 2 Single', 3, 48, 4, 'room_suite'),
        ],
    },
    {
        'name': 'Lake View Resort',
        'city': 'Kerala',
        'country': 'India',
        'address': 'Vembanad Lake, Alleppey, Kerala, India',
        'star_rating': Decimal('4.0'),
        'price_per_night': Decimal('95.00'),
        'is_featured': True,
        'short_description': 'Backwater villas with private houseboat cruises.',
        'description': (
            'Set on the edge of Vembanad Lake, Lake View Resort offers traditional Kerala architecture, '
            'an Ayurvedic spa and sunset houseboat cruises.'
        ),
        'highlights': ['Backwater Views', 'Ayurvedic Spa', 'Houseboat Cruises', 'Organic Kitchen'],
        'amenities': ['Free WiFi', 'Swimming Pool', 'Spa & Wellness', 'Restaurant'],
        'images': ['lake_view', 'lake_view_2', 'lake_view_3'],
        'rooms': [
            ('Garden Villa', 'villa', Decimal('95.00'), 2, 3, '1 King Bed', 1, 34, 7, 'room_deluxe'),
            ('Lake Villa', 'villa', Decimal('140.00'), 3, 4, '1 King Bed', 1, 46, 4, 'room_premium'),
        ],
    },
    {
        'name': 'City Central Hotel',
        'city': 'Bangalore',
        'country': 'India',
        'address': 'MG Road, Bangalore, India',
        'star_rating': Decimal('4.0'),
        'price_per_night': Decimal('80.00'),
        'is_featured': False,
        'short_description': 'Business-ready hotel in the heart of the city.',
        'description': (
            'City Central Hotel is built for travellers who need to be close to everything: metro access, '
            'a 24-hour business centre and a rooftop restaurant.'
        ),
        'highlights': ['Metro at the Door', '24h Business Centre', 'Rooftop Restaurant', 'Gym'],
        'amenities': ['Free WiFi', 'Restaurant', 'Room Service', 'Parking'],
        'images': ['city_central', 'city_central_2', 'city_central_3'],
        'rooms': [
            ('Smart Room', 'standard', Decimal('80.00'), 2, 2, '1 Queen Bed', 1, 24, 12, 'room_king'),
            ('Business Suite', 'premium', Decimal('125.00'), 2, 3, '1 King Bed + Desk', 1, 40, 5, 'room_premium'),
        ],
    },
]

TESTIMONIALS = [
    {
        'name': 'Sarah Johnson', 'location': 'New York, USA', 'rating': 5, 'avatar': 'avatar_sarah',
        'hotel': 'Grand Vista Resort',
        'message': '"Amazing experience! The hotel was beautiful, clean and the staff was very friendly. Highly recommended."',
    },
    {
        'name': 'Michael Chan', 'location': 'Singapore', 'rating': 5, 'avatar': 'avatar_michael',
        'hotel': 'Royal Palm Hotel',
        'message': '"Perfect location and great amenities. The view from our room was absolutely breathtaking."',
    },
    {
        'name': 'Priya Sharma', 'location': 'Mumbai, India', 'rating': 4, 'avatar': 'avatar_priya',
        'hotel': 'Ocean Breeze Resort',
        'message': '"Best hotel booking experience ever. Easy process and excellent customer support. Will definitely book again!"',
    },
]

# (hotel, user_key, nights_from_now, nights, rating, title, comment, status)
DEMO_REVIEWS = [
    ('Grand Vista Resort', 'sarah', 2, 5, 'Dreamy beachfront stay',
     'The infinity pool overlooking the ocean is worth the trip alone. Staff remembered our names by day two.'),
    ('Grand Vista Resort', 'michael', 4, 5, 'Faultless service',
     'Spotless rooms, brilliant breakfast spread and a spa that is genuinely world class.'),
    ('Grand Vista Resort', 'priya', 3, 4, 'Beautiful resort, busy at weekends',
     'Loved the gardens and the beach access. Pools get busy on Saturday afternoons.'),
    ('Royal Palm Hotel', 'michael', 5, 5, 'Best view in Dubai',
     'The rooftop pool at sunset is unforgettable. Rooms are quiet despite the central location.'),
    ('Royal Palm Hotel', 'sarah', 3, 4, 'Great for business travel',
     'Fast Wi-Fi, a proper desk and the airport transfer was on time.'),
    ('Ocean Breeze Resort', 'priya', 4, 5, 'Perfect family holiday',
     'Steps from the sand, friendly staff and the kids loved the pool.'),
    ('Ocean Breeze Resort', 'sarah', 5, 4, 'Relaxed and good value',
     'Simple rooms but everything works, and the beach bar is lovely in the evening.'),
    ('Mountain View Hotel', 'michael', 6, 5, 'Stunning mountain views',
     'Woke up to snow on the peaks. The fireplace lounge is very cosy.'),
    ('Mountain View Hotel', 'priya', 4, 4, 'Lovely stay, bring layers',
     'Great trekking advice from the front desk. Rooms are warm even in winter.'),
    ('Lake View Resort', 'sarah', 5, 4, 'Peaceful backwater escape',
     'The houseboat cruise at sunset was the highlight of our trip.'),
    ('Lake View Resort', 'michael', 6, 5, 'Authentic Kerala hospitality',
     'Wonderful Ayurvedic treatments and the food was outstanding.'),
    ('City Central Hotel', 'priya', 3, 4, 'Handy for the office',
     'Metro is right outside, check-in was quick and the rooftop restaurant is good.'),
]


class Command(BaseCommand):
    help = 'Populate the database with dynamic demo content for the frontend.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete existing demo content before seeding.',
        )
        parser.add_argument(
            '--no-users', action='store_true',
            help='Skip creating the demo customer accounts.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write('Flushing existing content...')
            Review.objects.all().delete()
            Booking.objects.all().delete()
            RoomImage.objects.all().delete()
            Room.objects.all().delete()
            HotelImage.objects.all().delete()
            Hotel.objects.all().delete()
            GalleryImage.objects.all().delete()
            TextSection.objects.all().delete()
            ContactCard.objects.all().delete()
            ContactFaq.objects.all().delete()
            Testimonial.objects.all().delete()
            HeroBanner.objects.all().delete()
            Feature.objects.all().delete()
            NavLink.objects.all().delete()

        settings_obj = self.seed_settings()
        self.seed_contact()
        self.seed_nav()
        self.seed_heroes()
        self.seed_features()
        self.seed_text_sections(settings_obj)
        amenities = self.seed_amenities()
        hotels = self.seed_hotels(amenities)
        self.seed_testimonials(hotels)

        users = {}
        if not options['no_users']:
            users = self.seed_users()
            self.seed_bookings(users, hotels)
        self.seed_reviews(hotels, users)

        self.stdout.write(self.style.SUCCESS('Seed complete.'))
        self.stdout.write(
            f'  Site settings: {settings_obj.site_title} | '
            f'Hotels: {Hotel.objects.count()} | Rooms: {Room.objects.count()} | '
            f'Bookings: {Booking.objects.count()} | Reviews: {Review.objects.count()}'
        )

    # -- content ---------------------------------------------------------
    def seed_settings(self):
        obj = SiteSettings.load()
        obj.site_title = 'SkyStay'
        obj.tagline = 'Hotels & Resorts'
        obj.footer_text = '© 2025 SkyStay. All rights reserved.'
        obj.meta_description = (
            'SkyStay — discover luxury hotels and resorts worldwide. Search by destination, '
            'compare rooms and book instantly.'
        )
        obj.contact_email = 'info@skystay.com'
        obj.contact_phone = '+91 98765 43210'
        obj.address = '123 Beach Road, Bali, Indonesia'
        obj.currency_code = 'INR'
        obj.currency_symbol = '₹'
        obj.tax_percentage = Decimal('0.00')
        obj.default_check_in_time = '14:00'
        obj.default_check_out_time = '11:00'
        obj.save()
        return obj

    def seed_contact(self):
        """The Contact page CMS: settings, the three contact cards and FAQs."""
        contact = ContactSettings.load()
        contact.page_title = 'Contact us'
        contact.intro_message = (
            'Reach out using the details below — our team replies within one business day.'
        )
        contact.response_time = 'Our team replies within one business day.'
        contact.intro_enabled = True
        contact.email = 'info@skystay.com'
        contact.phone = '+91 98765 43210'
        contact.support_hours = '24/7'
        contact.property_name = 'SkyStay'
        contact.address = '123 Beach Road'
        contact.city = 'Bali'
        contact.country = 'Indonesia'
        contact.postal_code = '80361'
        contact.latitude = Decimal('-8.409518')
        contact.longitude = Decimal('115.188919')
        contact.map_enabled = True
        contact.primary_cta_text = 'Browse hotels'
        contact.primary_cta_link = '/hotels'
        contact.secondary_cta_text = 'Contact Support'
        contact.secondary_cta_link = '/dashboard/bookings'
        contact.booking_support_enabled = True
        contact.booking_support_title = 'Need help with a booking?'
        contact.booking_support_description = (
            'Have your booking reference ready and we will help you with changes, cancellations '
            'or special requests.'
        )
        contact.booking_support_button_text = 'Manage my booking'
        contact.booking_support_button_link = '/dashboard/bookings'
        contact.support_enabled = True
        contact.support_title = 'Guest support'
        contact.support_description = (
            'Already travelling? Our reservations team is reachable around the clock for '
            'changes, late arrivals and on-property requests.'
        )
        contact.cards_enabled = True
        contact.contact_form_enabled = True
        contact.form_phone_enabled = True
        contact.form_phone_required = True
        contact.faq_enabled = True
        contact.save()

        cards = [
            (ContactCard.Kind.EMAIL, 'Email us', 'Reservations, changes and group bookings.', ''),
            (ContactCard.Kind.PHONE, 'Call us', 'Available 24/7 for guests already travelling.', ''),
            (ContactCard.Kind.LOCATION, 'Hotel Location', '', 'View on Map'),
        ]
        for index, (kind, title, description, cta_label) in enumerate(cards):
            ContactCard.objects.update_or_create(
                kind=kind,
                defaults={
                    'title': title,
                    'description': description,
                    'cta_label': cta_label,
                    'order': index,
                    'is_active': True,
                },
            )

        faqs = [
            (
                'How do I modify my booking?',
                'Open My Bookings in your dashboard, choose the reservation and update the dates, '
                'guests or special requests. Availability and pricing are recalculated instantly.',
            ),
            (
                'How can I cancel my reservation?',
                'Go to My Bookings, open the reservation and select Cancel booking. The confirmation '
                'email in your inbox is updated as soon as the cancellation goes through.',
            ),
            (
                'Where can I find my booking confirmation?',
                'Your confirmation reference (SKY-XXXXXX) is emailed the moment the booking is placed '
                'and is always available under My Bookings in your account.',
            ),
            (
                'Can I request early check-in?',
                'Yes. Add it to the special requests when booking, or contact us with your booking '
                'reference and we will ask the property to hold the room early.',
            ),
            (
                'How do I contact a hotel directly?',
                'Every hotel page lists the property address. For anything urgent, use the phone '
                'number on this page and our team will connect you to the property.',
            ),
        ]
        for index, (question, answer) in enumerate(faqs):
            ContactFaq.objects.update_or_create(
                question=question,
                defaults={'answer': answer, 'order': index, 'is_active': True},
            )

    def seed_nav(self):
        links = [
            ('Home', '/', NavLink.Location.HEADER),
            ('Hotels', '/hotels', NavLink.Location.HEADER),
            ('About', '/about', NavLink.Location.HEADER),
            ('Offers', '/offers', NavLink.Location.HEADER),
            ('Contact', '/contact', NavLink.Location.HEADER),
            ('Hotels', '/hotels', NavLink.Location.FOOTER),
            ('About us', '/about', NavLink.Location.FOOTER),
            ('Offers', '/offers', NavLink.Location.FOOTER),
            ('Contact', '/contact', NavLink.Location.FOOTER),
            ('Privacy Policy', '/privacy', NavLink.Location.FOOTER_LEGAL),
            ('Terms of Service', '/terms', NavLink.Location.FOOTER_LEGAL),
            ('Cookie Policy', '/cookies', NavLink.Location.FOOTER_LEGAL),
        ]
        for index, (label, url, location) in enumerate(links):
            NavLink.objects.update_or_create(
                label=label, url=url, location=location,
                defaults={'order': index, 'is_active': True},
            )

    def seed_heroes(self):
        HeroBanner.objects.update_or_create(
            title='Discover Your Perfect Stay',
            defaults={
                'eyebrow': 'Welcome to SkyStay',
                'subtitle': 'Luxury, comfort and unforgettable experiences at the world’s best hotels.',
                'description': (
                    'Browse hand-picked hotels and resorts, check live availability and confirm your '
                    'reservation in minutes.'
                ),
                'background_url': IMG['hero_bali'],
                'overlay_opacity': Decimal('0.55'),
                'cta_text': 'Explore hotels',
                'cta_link': '/hotels',
                'secondary_cta_text': 'View offers',
                'secondary_cta_link': '/offers',
                'show_search_form': True,
                'order': 0,
                'is_active': True,
            },
        )

    def seed_features(self):
        for index, (title, icon, description) in enumerate(FEATURES):
            Feature.objects.update_or_create(
                title=title,
                defaults={'icon': icon, 'description': description, 'order': index, 'is_active': True},
            )

    def seed_text_sections(self, settings_obj):
        sections = [
            {
                'key': TextSection.Key.FEATURED_HOTELS,
                'heading': 'Featured Hotels',
                'subheading': 'Handpicked hotels for your perfect getaway',
                'cta_text': 'View All Hotels',
                'cta_link': '/hotels',
            },
            {
                'key': TextSection.Key.HOTELS_LISTING,
                'heading': 'Hotels & Resorts',
                'subheading': 'Find the perfect stay for your next trip.',
                'body': 'Use the filters to narrow by destination, price, property rating and amenities.',
            },
            {
                'key': TextSection.Key.AMENITIES,
                'heading': 'Our Amenities',
                'subheading': 'Everything you need for a comfortable stay',
                'image_url': IMG['spa'],
            },
            {
                'key': TextSection.Key.TESTIMONIALS,
                'heading': 'What Our Guests Say',
                'subheading': 'Real experiences from our valued guests.',
            },
            {
                'key': TextSection.Key.ABOUT,
                'heading': 'Stay somewhere worth remembering',
                'subheading': 'Curated properties, transparent pricing, instant confirmation',
                'body': (
                    f'{settings_obj.site_title} works with independent hotels and resorts to keep '
                    'pricing honest and availability live. Every property is visited by our team '
                    'before it goes live, so what you see is what you get.'
                ),
                'image_url': IMG['hero_pool'],
                'cta_text': 'Browse destinations',
                'cta_link': '/hotels',
            },
            {
                'key': TextSection.Key.CTA,
                'heading': 'Ready for your next escape?',
                'subheading': 'Members unlock exclusive rates on every booking.',
                'cta_text': 'Create free account',
                'cta_link': '/register',
            },
            {
                'key': TextSection.Key.DASHBOARD,
                'heading': 'My Dashboard',
                'subheading': 'Welcome back to your travel hub',
            },
        ]
        for index, payload in enumerate(sections):
            key = payload.pop('key')
            TextSection.objects.update_or_create(
                key=key, defaults={**payload, 'order': index, 'is_active': True},
            )

        about = TextSection.objects.filter(key=TextSection.Key.ABOUT).first()
        if about:
            gallery = [
                ('Infinity pool', IMG['hero_pool']),
                ('Beachfront dining', IMG['restaurant']),
                ('Spa & wellness', IMG['spa']),
                ('Signature suites', IMG['room_suite']),
            ]
            for index, (title, url) in enumerate(gallery):
                GalleryImage.objects.update_or_create(
                    section=about, title=title,
                    defaults={'image_url': url, 'caption': title, 'order': index},
                )

    def seed_amenities(self):
        amenities = {}
        for index, (name, icon, description) in enumerate(AMENITIES):
            obj, _ = Amenity.objects.update_or_create(
                name=name,
                defaults={
                    'icon': icon,
                    'description': description,
                    'show_on_homepage': True,
                    'order': index,
                    'is_active': True,
                },
            )
            amenities[name] = obj
        return amenities

    # -- catalogue -------------------------------------------------------
    def seed_hotels(self, amenities):
        hotels = {}
        for payload in HOTELS:
            data = {k: v for k, v in payload.items() if k not in ('amenities', 'images', 'rooms')}
            # The first gallery image doubles as the listing card cover.
            data['cover_image_url'] = IMG[payload['images'][0]]
            hotel, _ = Hotel.objects.update_or_create(name=payload['name'], defaults=data)
            hotel.amenities.set([amenities[name] for name in payload['amenities'] if name in amenities])

            for index, key in enumerate(payload['images']):
                HotelImage.objects.update_or_create(
                    hotel=hotel, order=index,
                    defaults={'image_url': IMG[key], 'alt_text': f'{hotel.name} photo {index + 1}'},
                )

            for order, spec in enumerate(payload['rooms']):
                name, room_type, price, capacity, max_guests, bed_type, beds, size, total, cover = spec
                room, _ = Room.objects.update_or_create(
                    hotel=hotel, name=name,
                    defaults={
                        'room_type': room_type,
                        'price_per_night': price,
                        'capacity': capacity,
                        'max_guests': max_guests,
                        'bed_type': bed_type,
                        'beds': beds,
                        'size_sqm': size,
                        'total_rooms': total,
                        'cover_image_url': IMG[cover],
                        'description': (
                            f'{name} at {hotel.name}. {bed_type}, {size} m², sleeps up to {max_guests} guests. '
                            'Includes complimentary Wi-Fi, daily housekeeping and access to all hotel facilities.'
                        ),
                        'order': order,
                        'is_active': True,
                    },
                )
                room.amenity_list.set(list(amenities.values())[: 3 + (order % 3)])
                for image_index, key in enumerate([cover, 'room_bath', 'room_balcony']):
                    RoomImage.objects.update_or_create(
                        room=room, order=image_index,
                        defaults={'image_url': IMG[key], 'alt_text': f'{room.name} photo {image_index + 1}'},
                    )
            hotels[payload['name']] = hotel
        return hotels

    def seed_testimonials(self, hotels):
        for index, payload in enumerate(TESTIMONIALS):
            Testimonial.objects.update_or_create(
                name=payload['name'],
                defaults={
                    'location': payload['location'],
                    'rating': payload['rating'],
                    'message': payload['message'],
                    'avatar_url': IMG[payload['avatar']],
                    'hotel': hotels.get(payload['hotel']),
                    'order': index,
                    'is_active': True,
                },
            )

    # -- users, bookings, reviews ----------------------------------------
    def seed_users(self):
        users = {}

        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@skystay.com',
                'first_name': 'Site',
                'last_name': 'Admin',
                'role': User.Role.HOTEL_ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin.set_password('admin12345')
            admin.save()
            self.stdout.write(self.style.WARNING('Created superuser admin / admin12345 — change this password.'))

        demo_specs = [
            ('delyanka', 'Delyanka', 'P', 'delyanka@example.com', 'avatar_delyanka'),
            ('sarah', 'Sarah', 'Johnson', 'sarah@example.com', 'avatar_sarah'),
            ('michael', 'Michael', 'Chan', 'michael@example.com', 'avatar_michael'),
            ('priya', 'Priya', 'Sharma', 'priya@example.com', 'avatar_priya'),
        ]
        for username, first, last, email, avatar in demo_specs:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                    'phone': '+1 555 0100',
                    'city': 'Bali',
                    'country': 'Indonesia',
                    'avatar_url': IMG[avatar],
                },
            )
            if created:
                user.set_password('demo12345')
                user.save()
            users[username] = user
        return users

    def seed_bookings(self, users, hotels):
        """One upcoming stay plus a couple of completed ones, so the dashboard has data."""
        today = timezone.localdate()
        demo = users.get('delyanka')
        if not demo:
            return

        room = hotels['Royal Palm Hotel'].rooms.get(name='Deluxe Room')
        upcoming, _ = Booking.objects.update_or_create(
            user=demo, room=room, check_in=today + timedelta(days=7),
            defaults={
                'check_out': today + timedelta(days=10),
                'guests': 2,
                'rooms_count': 1,
                'status': Booking.Status.CONFIRMED,
                'special_requests': 'High floor with a marina view, please.',
                'guest_name': demo.display_name,
                'guest_email': demo.email,
                'guest_phone': demo.phone,
            },
        )
        upcoming.save()

        history = [
            ('Grand Vista Resort', 'Deluxe Room', 45, 3, Booking.Status.COMPLETED),
            ('Ocean Breeze Resort', 'Standard Room', 90, 4, Booking.Status.COMPLETED),
            ('Mountain View Hotel', 'Deluxe Valley Room', 130, 2, Booking.Status.CANCELLED),
        ]
        for hotel_name, room_name, days_ago, nights, status in history:
            try:
                past_room = hotels[hotel_name].rooms.get(name=room_name)
            except Room.DoesNotExist:  # pragma: no cover - seed data drift
                continue
            check_in = today - timedelta(days=days_ago)
            booking, _ = Booking.objects.update_or_create(
                user=demo, room=past_room, check_in=check_in,
                defaults={
                    'check_out': check_in + timedelta(days=nights),
                    'guests': 2,
                    'rooms_count': 1,
                    'status': status,
                    'guest_name': demo.display_name,
                    'guest_email': demo.email,
                    'guest_phone': demo.phone,
                },
            )
            booking.save()

    def seed_reviews(self, hotels, users):
        for hotel_name, user_key, days_ago, rating, title, comment in DEMO_REVIEWS:
            hotel = hotels.get(hotel_name)
            if not hotel:
                continue
            user = users.get(user_key)
            Review.objects.update_or_create(
                hotel=hotel, title=title,
                defaults={
                    'user': user,
                    'rating': rating,
                    'comment': comment,
                    'is_approved': True,
                },
            )

        # Refresh the denormalised aggregates once all reviews exist.
        for hotel in hotels.values():
            hotel.recalculate_rating()
