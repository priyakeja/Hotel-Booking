from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class Review(TimeStampedModel):
    """A guest review attached to a hotel (and optionally to a booking)."""

    hotel = models.ForeignKey('hotels.Hotel', on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True
    )
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='review',
    )
    rating = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=160, blank=True)
    comment = models.TextField()
    is_approved = models.BooleanField(default=True, help_text='Uncheck to hide from the public site.')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        constraints = [
            models.UniqueConstraint(fields=['user', 'booking'], name='one_review_per_booking'),
        ]

    def __str__(self):
        return f'{self.hotel.name} — {self.rating}★ by {self.author_name}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Keep the hotel's denormalised aggregates in sync for listing pages.
        self.hotel.recalculate_rating()

    def delete(self, *args, **kwargs):
        hotel = self.hotel
        super().delete(*args, **kwargs)
        hotel.recalculate_rating()

    @property
    def author_name(self):
        if self.user:
            return self.user.display_name
        return 'Guest'
