from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel, media_upload_path


class User(AbstractUser, TimeStampedModel):
    """Custom user. Customers book rooms, hotel admins manage the CMS."""

    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        HOTEL_ADMIN = 'hotel_admin', 'Hotel Administrator'

    email = models.EmailField('email address', unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    phone = models.CharField(max_length=32, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    avatar = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    marketing_opt_in = models.BooleanField(default=False)

    REQUIRED_FIELDS = ['email']

    class Meta:
        ordering = ['-date_joined']

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def is_hotel_admin(self):
        return self.role == self.Role.HOTEL_ADMIN or self.is_superuser

    @property
    def booking_count(self):
        return self.bookings.count()
