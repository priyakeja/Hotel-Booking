"""Abstract building blocks reused by every app's models."""

import os
import uuid

from django.core.cache import cache
from django.db import models


def media_upload_path(instance, filename):
    """Store uploads under ``<app>/<model>/<uuid>-<filename>``.

    Keeps user supplied filenames from colliding and keeps the media folder
    organised the same way the admin exposes it.
    """
    ext = os.path.splitext(filename)[1].lower()
    safe_name = f'{uuid.uuid4().hex}{ext}'
    app_label = instance._meta.app_label
    model_name = instance._meta.model_name
    return os.path.join(app_label, model_name, safe_name)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrderedModel(models.Model):
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ['order', 'id']


class ImageAsset(TimeStampedModel):
    """An image that may be uploaded through the admin *or* linked remotely.

    ``image`` wins when a file has been uploaded, otherwise ``image_url`` is
    used. This keeps demo content working out of the box while still letting the
    administrator replace every visual from the CMS.
    """

    image = models.ImageField(upload_to=media_upload_path, blank=True, null=True)
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text='Optional external image URL. Used when no file is uploaded above.',
    )
    caption = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)

    class Meta:
        abstract = True
        ordering = ['order', 'id']

    def __str__(self):
        return self.caption or self.alt_text or f'Image #{self.pk}'


class SingletonModel(models.Model):
    """A model with exactly one row, edited through the Django admin."""

    CACHE_KEY = None

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Pinning the pk means every save targets row 1: an existing singleton is
        # updated rather than duplicated, and ``load()`` can never see two rows.
        self.pk = 1

        if self._state.adding:
            existing = type(self).objects.filter(pk=1).first()
            if existing is not None:
                # A brand new instance is being saved over the existing row. Django only
                # populates auto_now_add fields on INSERT, so carry the original creation
                # timestamp across to avoid writing NULL into a non-nullable column.
                self._state.adding = False
                for field in self._meta.concrete_fields:
                    if getattr(field, 'auto_now_add', False) and getattr(self, field.attname, None) is None:
                        setattr(self, field.attname, getattr(existing, field.attname))

        super().save(*args, **kwargs)
        cache.delete(self.cache_key())

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete(self.cache_key())

    @classmethod
    def cache_key(cls):
        return cls.CACHE_KEY or f'{cls._meta.app_label}.{cls._meta.model_name}'

    @classmethod
    def load(cls):
        """Fetch the singleton row, memoised in the cache to avoid a query per request."""
        key = cls.cache_key()
        obj = cache.get(key)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(key, obj, 600)
        return obj
