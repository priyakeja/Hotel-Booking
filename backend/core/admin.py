"""Reusable admin building blocks (image previews, singleton guards)."""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe


def image_thumbnail(uploaded, external_url='', height=56, width=84):
    """Render an inline <img> preview for an uploaded or external image."""
    src = ''
    if uploaded:
        try:
            src = uploaded.url
        except ValueError:  # file field without a file
            src = ''
    src = src or external_url
    if not src:
        # A static placeholder: `format_html` requires interpolation args, so use
        # `mark_safe` for this trusted literal instead.
        return mark_safe('<span style="color:#999;">—</span>')
    return format_html(
        '<img src="{}" style="height:{}px;width:{}px;object-fit:cover;'
        'border-radius:6px;border:1px solid #ddd;" />',
        src, height, width,
    )


class ImagePreviewAdminMixin:
    """Adds `preview_<field>` helpers that admin list_display can reference."""

    preview_height = 56
    preview_width = 84

    def _preview(self, uploaded, external):
        return image_thumbnail(uploaded, external, self.preview_height, self.preview_width)

    def cover_preview(self, obj):
        return self._preview(getattr(obj, 'cover_image', None), getattr(obj, 'cover_image_url', ''))

    cover_preview.short_description = 'Cover'

    def image_preview(self, obj):
        return self._preview(getattr(obj, 'image', None), getattr(obj, 'image_url', ''))

    image_preview.short_description = 'Image'

    def background_preview(self, obj):
        return self._preview(getattr(obj, 'background', None), getattr(obj, 'background_url', ''))

    background_preview.short_description = 'Background'


class SingletonAdmin(admin.ModelAdmin):
    """Admin for models that must only ever have a single row."""

    def has_add_permission(self, request):
        return not self.model.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
