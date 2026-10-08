from rest_framework import serializers

from core.utils import resolve_image


class ResolvedImageMixin:
    """Adds helpers so serializers can emit one usable image URL.

    The API always returns a single ``image`` key per image, already resolved to
    an absolute URL — preferring the uploaded file, falling back to the external
    URL configured in the CMS.
    """

    def resolved(self, uploaded_field, external_url, request=None):
        request = request or self.context.get('request')
        return resolve_image(request, uploaded_field, external_url)


class AbsoluteImageField(serializers.ImageField):
    """ImageField that renders an absolute URL instead of a relative one."""

    def to_representation(self, value):
        if not value:
            return None
        request = self.context.get('request')
        url = value.url
        return request.build_absolute_uri(url) if request else url
