from decimal import Decimal

from django.db import models
from django.db.models import Avg, Count
from django.utils.text import slugify

from content.models import Amenity
from core.models import ImageAsset, OrderedModel, TimeStampedModel, media_upload_path


class Hotel(TimeStampedModel):
    """A property that customers can browse, filter and book."""

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    city = models.CharField(max_length=120, db_index=True)
    state = models.CharField(max_length=120, blank=True, db_index=True)
    country = models.CharField(max_length=120, db_index=True)
    address = models.CharField(max_length=255, blank=True)
    short_description = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    star_rating = models.DecimalField(max_digits=2, decimal_places=1, default=Decimal('4.0'))
    price_per_night = models.DecimalField(
        max_digits=10, decimal_places=2, help_text='Displayed "from" price on listing cards.'
    )
    cover_image = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    cover_image_url = models.URLField(max_length=500, blank=True)
    highlights = models.TextField(
        blank=True, help_text='One highlight per line. Shown in the hotel detail sidebar.'
    )
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='hotels')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)

    # Denormalised review aggregates. Kept in sync by Review.save()/delete() so
    # listing pages never need a per-hotel aggregate query.
    rating_average = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('0'), db_index=True)
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-is_featured', 'name']
        verbose_name = 'Hotel'
        verbose_name_plural = 'Hotels'

    def __str__(self):
        return f'{self.name} — {self.city}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.name}-{self.city}')[:160]
            slug = base
            counter = 1
            while Hotel.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f'{base}-{counter}'
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def highlight_list(self):
        return [line.strip() for line in (self.highlights or '').splitlines() if line.strip()]

    @property
    def location(self):
        return f'{self.city}, {self.country}'

    @property
    def average_rating(self):
        return float(self.rating_average or 0)

    def recalculate_rating(self, save=True):
        """Recompute the denormalised review aggregates for this hotel."""
        stats = self.reviews.filter(is_approved=True).aggregate(
            average=Avg('rating'), total=Count('id')
        )
        self.rating_average = Decimal(str(round(stats['average'] or 0, 1)))
        self.review_count = stats['total'] or 0
        if save and self.pk:
            Hotel.objects.filter(pk=self.pk).update(
                rating_average=self.rating_average, review_count=self.review_count
            )
        return self.rating_average, self.review_count

    @property
    def active_rooms(self):
        return self.rooms.filter(is_active=True)


class HotelImage(ImageAsset):
    """Gallery image belonging to a hotel."""

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='images')

    class Meta(ImageAsset.Meta):
        verbose_name = 'Hotel image'
        verbose_name_plural = 'Hotel images'

    def __str__(self):
        return f'{self.hotel.name} — {super().__str__()}'


class Room(OrderedModel, TimeStampedModel):
    """A bookable room category inside a hotel."""

    class RoomType(models.TextChoices):
        STANDARD = 'standard', 'Standard'
        DELUXE = 'deluxe', 'Deluxe'
        PREMIUM = 'premium', 'Premium'
        SUITE = 'suite', 'Suite'
        VILLA = 'villa', 'Villa'

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=160)
    room_type = models.CharField(max_length=20, choices=RoomType.choices, default=RoomType.DELUXE)
    description = models.TextField(blank=True)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    capacity = models.PositiveSmallIntegerField(default=2, help_text='Adults included in the price.')
    max_guests = models.PositiveSmallIntegerField(default=3, help_text='Hard limit including children.')
    bed_type = models.CharField(max_length=80, blank=True, help_text='e.g. 1 King Bed')
    beds = models.PositiveSmallIntegerField(default=1)
    size_sqm = models.PositiveSmallIntegerField(default=30)
    total_rooms = models.PositiveSmallIntegerField(
        default=5, help_text='Number of identical rooms available for sale.'
    )
    amenity_list = models.ManyToManyField(Amenity, blank=True, related_name='rooms')
    cover_image = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    cover_image_url = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta(OrderedModel.Meta):
        verbose_name = 'Room'
        verbose_name_plural = 'Rooms'

    def __str__(self):
        return f'{self.hotel.name} — {self.name}'

    @property
    def amenities(self):
        """Alias used by the API/serializers."""
        return self.amenity_list


class RoomImage(ImageAsset):
    """Gallery image belonging to a room."""

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='images')

    class Meta(ImageAsset.Meta):
        verbose_name = 'Room image'
        verbose_name_plural = 'Room images'

    def __str__(self):
        return f'{self.room.name} — {super().__str__()}'


class NearbyFacility(TimeStampedModel):
    """Point of interest near a hotel (airport, station, beach, hospital...)."""

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='nearby_facilities')
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=80, blank=True, help_text='e.g. Airport, Transit, Attraction, Beach')
    description = models.TextField(blank=True)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, help_text='Distance from hotel in kilometres.')
    icon = models.CharField(max_length=60, blank=True, help_text='Icon keyword e.g. map-pin, compass, plane...')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'distance_km']
        verbose_name = 'Nearby facility'
        verbose_name_plural = 'Nearby facilities'

    def __str__(self):
        return f'{self.name} ({self.distance_km} km) — {self.hotel.name}'

