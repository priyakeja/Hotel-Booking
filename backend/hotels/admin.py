from django import forms
from django.contrib import admin

from core.admin import ImagePreviewAdminMixin
from core.widgets import LocationMapWidget
from hotels.models import Hotel, HotelImage, NearbyFacility, Room, RoomImage


class NearbyFacilityInline(admin.TabularInline):
    model = NearbyFacility
    extra = 1
    fields = ('name', 'category', 'distance_km', 'icon', 'is_active', 'order')
    ordering = ('order', 'distance_km')


class HotelImageInline(admin.TabularInline):

    model = HotelImage
    extra = 1
    fields = ('image', 'image_url', 'caption', 'alt_text', 'order')
    ordering = ('order',)


class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 1
    fields = ('image', 'image_url', 'caption', 'alt_text', 'order')
    ordering = ('order',)


class RoomInline(admin.StackedInline):
    model = Room
    extra = 0
    show_change_link = True
    fields = (
        'name', 'room_type', 'price_per_night', 'capacity', 'max_guests',
        'bed_type', 'beds', 'size_sqm', 'total_rooms', 'is_active', 'order',
    )


class HotelAdminForm(forms.ModelForm):
    """Reuses the contact page's map picker so a property can be placed on the map.

    Its coordinates are what the Contact page publishes when the Contact
    settings are linked to this hotel.
    """

    map_picker = forms.CharField(
        required=False,
        label='Pick the point on the map',
        widget=LocationMapWidget(attrs={'id': 'skystay-hotel-map'}),
        help_text='Search, click or drag the marker. The coordinates above update automatically.',
    )

    class Meta:
        model = Hotel
        fields = '__all__'


@admin.register(Hotel)
class HotelAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    form = HotelAdminForm
    list_display = (
        'cover_preview', 'name', 'city', 'state', 'country', 'star_rating',
        'price_per_night', 'rating_average', 'review_count', 'is_featured', 'is_active',
    )
    list_display_links = ('name',)
    list_editable = ('price_per_night', 'is_featured', 'is_active')
    list_filter = ('is_active', 'is_featured', 'star_rating', 'country', 'state', 'city')
    search_fields = ('name', 'city', 'state', 'country', 'address', 'description')
    prepopulated_fields = {'slug': ('name', 'city')}
    filter_horizontal = ('amenities',)
    inlines = [HotelImageInline, RoomInline, NearbyFacilityInline]
    save_on_top = True
    fieldsets = (
        ('Identity', {'fields': ('name', 'slug', 'short_description', 'description')}),
        ('Location', {'fields': ('city', 'state', 'country', 'address', 'latitude', 'longitude', 'map_picker')}),
        ('Pricing & rating', {'fields': ('price_per_night', 'star_rating', 'rating_average', 'review_count')}),
        ('Cover image', {'fields': ('cover_image', 'cover_image_url')}),
        ('Highlights', {
            'fields': ('highlights', 'amenities'),
            'description': 'Highlights: one per line. They render as the bullet list on the hotel page.',
        }),
        ('Visibility', {'fields': ('is_featured', 'is_active')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('images', 'amenities', 'nearby_facilities')


@admin.register(Room)
class RoomAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = (
        'cover_preview', 'name', 'hotel', 'room_type', 'price_per_night',
        'capacity', 'max_guests', 'total_rooms', 'is_active', 'order',
    )
    list_display_links = ('name',)
    list_editable = ('price_per_night', 'total_rooms', 'is_active', 'order')
    list_filter = ('is_active', 'room_type', 'hotel')
    search_fields = ('name', 'hotel__name', 'bed_type')
    autocomplete_fields = ('hotel',)
    filter_horizontal = ('amenity_list',)
    inlines = [RoomImageInline]
    fieldsets = (
        ('Room', {'fields': ('hotel', 'name', 'room_type', 'description')}),
        ('Pricing & capacity', {
            'fields': ('price_per_night', 'capacity', 'max_guests', 'bed_type', 'beds', 'size_sqm'),
        }),
        ('Inventory', {
            'fields': ('total_rooms', 'is_active', 'order'),
            'description': 'Total rooms controls how many can be booked for the same dates.',
        }),
        ('Media & amenities', {'fields': ('cover_image', 'cover_image_url', 'amenity_list')}),
    )


@admin.register(HotelImage)
class HotelImageAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = ('image_preview', 'hotel', 'caption', 'order')
    list_editable = ('order',)
    list_filter = ('hotel',)
    search_fields = ('hotel__name', 'caption')
    autocomplete_fields = ('hotel',)


@admin.register(RoomImage)
class RoomImageAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = ('image_preview', 'room', 'caption', 'order')
    list_editable = ('order',)
    list_filter = ('room__hotel', 'room')
    search_fields = ('room__name', 'caption')
    autocomplete_fields = ('room',)


@admin.register(NearbyFacility)
class NearbyFacilityAdmin(admin.ModelAdmin):
    list_display = ('name', 'hotel', 'category', 'distance_km', 'icon', 'is_active', 'order')
    list_editable = ('distance_km', 'is_active', 'order')
    list_filter = ('is_active', 'category', 'hotel')
    search_fields = ('name', 'category', 'hotel__name')
    autocomplete_fields = ('hotel',)

