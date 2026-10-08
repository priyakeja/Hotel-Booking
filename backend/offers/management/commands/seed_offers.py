"""Seed a realistic set of offers / promotion categories.

Idempotent: safe to run repeatedly. Everything it creates is normal database
content that the administrator can edit or delete from the admin panel.

    python manage.py seed_offers
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from hotels.models import Hotel
from offers.models import Offer, OfferBenefit, OfferCategory, OfferSettings

CATEGORIES = [
    ('Limited Time', 'clock'),
    ('Early Bird', 'sparkles'),
    ('Weekend', 'calendar'),
    ('Long Stay', 'clock'),
    ('Last Minute', 'trending-up'),
    ('Couples', 'heart'),
    ('Family', 'users'),
    ('Seasonal', 'globe'),
    ('Luxury', 'award'),
]

BENEFITS = {
    'weekend-escape': ['Free Breakfast', 'Free WiFi', 'Free cancellation'],
    'early-bird-grand-vista': ['Room Upgrade (subject to availability)', 'Free Breakfast'],
    'goa-long-stay': ['Free Airport Transfer', 'Late Checkout', 'Free WiFi'],
    'dubai-luxury-escape': ['Executive Lounge Access', 'Complimentary Spa Credit', 'Free cancellation'],
    'kerala-last-minute': ['Welcome Drink', 'Free Breakfast'],
    'himachal-free-night': ['Free Breakfast', 'Kids Stay Free'],
}


class Command(BaseCommand):
    help = 'Seed sample offer categories and offers against existing hotels.'

    def handle(self, *args, **options):
        # Make sure the singleton settings row exists for the admin to edit.
        OfferSettings.load()

        today = timezone.localdate()

        categories = {}
        for index, (name, icon) in enumerate(CATEGORIES):
            category, _ = OfferCategory.objects.update_or_create(
                name=name,
                defaults={'icon': icon, 'order': index, 'is_active': True},
            )
            categories[name] = category

        hotels = {hotel.slug: hotel for hotel in Hotel.objects.all()}

        def image_for(hotel):
            if not hotel:
                return ''
            if hotel.cover_image_url:
                return hotel.cover_image_url
            first = hotel.images.first()
            return first.image_url if first else ''

        specs = [
            dict(
                slug='weekend-escape',
                hotel_slug='grand-vista-resort-bali',
                title='Weekend Escape',
                short_description='Stay 2 nights and save 30% on selected rooms.',
                description=(
                    'Escape for the weekend and save 30% on Deluxe and Premium rooms at '
                    'Grand Vista Resort. Includes daily breakfast for two.'
                ),
                category='Weekend',
                offer_type=Offer.OfferType.WEEKEND,
                discount_type=Offer.DiscountType.PERCENTAGE,
                discount_value=Decimal('30'),
                min_stay=2,
                featured=True,
                room_ids=[1, 2],
                end_days=30,
            ),
            dict(
                slug='early-bird-grand-vista',
                hotel_slug='grand-vista-resort-bali',
                title='Early Bird Saver',
                short_description='Book 30 days ahead and save 25%.',
                description='Plan ahead and lock in 25% off your stay when you book early.',
                category='Early Bird',
                offer_type=Offer.OfferType.EARLY_BIRD,
                discount_type=Offer.DiscountType.PERCENTAGE,
                discount_value=Decimal('25'),
                min_stay=1,
                featured=False,
                room_ids=[],
                end_days=45,
            ),
            dict(
                slug='goa-long-stay',
                hotel_slug='ocean-breeze-resort-goa',
                title='Long Stay Discount',
                short_description='Stay 5 nights or more and save 20%.',
                description='The longer you stay, the more you save. 20% off stays of 5 nights or more.',
                category='Long Stay',
                offer_type=Offer.OfferType.LONG_STAY,
                discount_type=Offer.DiscountType.PERCENTAGE,
                discount_value=Decimal('20'),
                min_stay=5,
                featured=True,
                room_ids=[],
                end_days=60,
            ),
            dict(
                slug='dubai-luxury-escape',
                hotel_slug='royal-palm-hotel-dubai',
                title='Luxury Escape',
                short_description='Executive Suite from ₹179/night.',
                description='Indulge in the Executive Suite at a special rate, with lounge access and a spa credit.',
                category='Luxury',
                offer_type=Offer.OfferType.LUXURY,
                discount_type=Offer.DiscountType.SPECIAL_PRICE,
                discount_value=Decimal('179'),
                min_stay=2,
                featured=True,
                room_ids=[5],
                end_days=30,
            ),
            dict(
                slug='kerala-last-minute',
                hotel_slug='lake-view-resort-kerala',
                title='Last-Minute Getaway',
                short_description='₹30 off any villa — book now, travel soon.',
                description='A last-minute treat: ₹30 off per night on every villa at Lake View Resort.',
                category='Last Minute',
                offer_type=Offer.OfferType.LAST_MINUTE,
                discount_type=Offer.DiscountType.FIXED,
                discount_value=Decimal('30'),
                min_stay=1,
                featured=False,
                room_ids=[],
                end_days=3,
            ),
            dict(
                slug='himachal-free-night',
                hotel_slug='mountain-view-hotel-manali',
                title='Family Free Night',
                short_description='Stay 3 nights, get the 4th night free.',
                description='Bring the family — book 3 nights and enjoy the 4th night on us.',
                category='Family',
                offer_type=Offer.OfferType.FAMILY,
                discount_type=Offer.DiscountType.FREE_NIGHT,
                discount_value=Decimal('0'),
                free_nights=1,
                min_stay=3,
                featured=False,
                room_ids=[],
                end_days=40,
            ),
        ]

        created = 0
        for order, spec in enumerate(specs):
            hotel = hotels.get(spec['hotel_slug'])
            if not hotel:
                self.stdout.write(self.style.WARNING(f"Hotel {spec['hotel_slug']} not found — skipped."))
                continue

            offer, _ = Offer.objects.update_or_create(
                slug=spec['slug'],
                defaults={
                    'title': spec['title'],
                    'short_description': spec['short_description'],
                    'description': spec['description'],
                    'category': categories.get(spec['category']),
                    'hotel': hotel,
                    'offer_type': spec['offer_type'],
                    'discount_type': spec['discount_type'],
                    'discount_value': spec['discount_value'],
                    'free_nights': spec.get('free_nights', 0),
                    'start_date': today - timedelta(days=2),
                    'end_date': today + timedelta(days=spec['end_days']),
                    'min_stay': spec['min_stay'],
                    'terms': (
                        f"Minimum {spec['min_stay']}-night stay.\n"
                        "Subject to availability.\n"
                        "Cannot be combined with other promotions.\n"
                        "Blackout dates may apply."
                    ),
                    'is_published': True,
                    'is_featured': spec['featured'],
                    'display_order': order,
                    'image_url': image_for(hotel),
                },
            )
            offer.rooms.set(spec['room_ids'])
            offer.benefits.all().delete()
            for b_index, text in enumerate(BENEFITS.get(spec['slug'], [])):
                OfferBenefit.objects.create(offer=offer, text=text, order=b_index)
            created += 1

        self.stdout.write(self.style.SUCCESS(f'Seeded {created} offers and {len(categories)} categories.'))
