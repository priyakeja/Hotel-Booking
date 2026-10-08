from django import forms
from django.contrib import admin

from content.models import (
    Amenity,
    ContactCard,
    ContactFaq,
    ContactMessage,
    ContactSettings,
    Feature,
    GalleryImage,
    HeroBanner,
    NavLink,
    SiteSettings,
    Testimonial,
    TextSection,
)
from core.admin import ImagePreviewAdminMixin, SingletonAdmin, image_thumbnail
from core.widgets import LocationMapWidget


@admin.register(SiteSettings)
class SiteSettingsAdmin(SingletonAdmin):
    """Branding, contact details — the single source of truth for the site chrome."""

    fieldsets = (
        ('Branding', {
            'fields': ('site_title', 'tagline', 'logo', 'logo_preview', 'logo_url', 'favicon', 'meta_description'),
        }),
        ('Footer & contact', {
            'fields': ('footer_text', 'contact_email', 'contact_phone', 'address'),
        }),
        ('Social links', {
            'fields': ('facebook_url', 'instagram_url', 'twitter_url', 'youtube_url'),
        }),
        ('Booking defaults', {
            'fields': (
                'currency_code', 'currency_symbol', 'tax_percentage',
                'default_check_in_time', 'default_check_out_time',
            ),
        }),
    )

    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        """Inline preview so the admin can confirm the logo before saving."""
        return image_thumbnail(obj.logo, obj.logo_url, 48, 140)

    logo_preview.short_description = 'Current logo'


@admin.register(NavLink)
class NavLinkAdmin(admin.ModelAdmin):
    list_display = ('label', 'url', 'location', 'order', 'is_active', 'open_in_new_tab')
    list_editable = ('order', 'is_active')
    list_filter = ('location', 'is_active')
    search_fields = ('label', 'url')


@admin.register(HeroBanner)
class HeroBannerAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = ('background_preview', 'title', 'eyebrow', 'order', 'is_active', 'show_search_form')
    list_display_links = ('title',)
    list_editable = ('order', 'is_active')
    search_fields = ('title', 'subtitle', 'description')
    fieldsets = (
        (None, {'fields': ('eyebrow', 'title', 'subtitle', 'description')}),
        ('Background', {'fields': ('background', 'background_url', 'overlay_opacity')}),
        ('Calls to action', {
            'fields': ('cta_text', 'cta_link', 'secondary_cta_text', 'secondary_cta_link'),
        }),
        ('Display', {'fields': ('show_search_form', 'order', 'is_active')}),
    )


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'description', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    search_fields = ('title', 'description')


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'show_on_homepage', 'order', 'is_active', 'hotel_total')
    list_editable = ('show_on_homepage', 'order', 'is_active')
    search_fields = ('name',)
    list_filter = ('show_on_homepage', 'is_active')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('hotels')

    def hotel_total(self, obj):
        return obj.hotels.count()

    hotel_total.short_description = 'Hotels'


class GalleryImageInline(admin.TabularInline):
    model = GalleryImage
    extra = 1
    fields = ('image', 'image_url', 'title', 'caption', 'alt_text', 'order')
    ordering = ('order',)


@admin.register(TextSection)
class TextSectionAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = ('key', 'heading', 'subheading', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('key', 'is_active')
    search_fields = ('heading', 'subheading', 'body')
    inlines = [GalleryImageInline]
    fieldsets = (
        (None, {'fields': ('key', 'eyebrow', 'heading', 'subheading', 'body')}),
        ('Imagery', {'fields': ('image', 'image_url')}),
        ('Call to action', {'fields': ('cta_text', 'cta_link')}),
        ('Display', {'fields': ('order', 'is_active')}),
    )


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('avatar_preview', 'name', 'location', 'rating', 'hotel', 'order', 'is_active')
    list_display_links = ('name',)
    list_editable = ('order', 'is_active')
    list_filter = ('rating', 'is_active', 'hotel')
    search_fields = ('name', 'location', 'message')
    autocomplete_fields = ('hotel',)

    def avatar_preview(self, obj):
        return image_thumbnail(obj.avatar, obj.avatar_url, 44, 44)

    avatar_preview.short_description = 'Avatar'


class ContactSettingsForm(forms.ModelForm):
    """Adds the interactive map picker on top of the model's own fields.

    ``map_picker`` is a form-only field: its widget reads and writes the
    latitude/longitude inputs, and nothing extra is persisted.
    """

    map_picker = forms.CharField(
        required=False,
        label='Pick the point on the map',
        widget=LocationMapWidget(attrs={'id': 'skystay-location-map'}),
        help_text='Search, click or drag the marker. The coordinates above update automatically.',
    )

    class Meta:
        model = ContactSettings
        fields = '__all__'


@admin.register(ContactSettings)
class ContactSettingsAdmin(SingletonAdmin):
    """The single source of truth for the Contact page and the footer.

    Every heading, contact detail, location and section toggle on the public
    Contact page is edited here, so content changes never need a deploy.
    """

    form = ContactSettingsForm
    save_on_top = True
    fieldsets = (
        ('General', {
            'fields': ('page_title', 'intro_message', 'response_time', 'intro_enabled'),
            'description': 'The page title, the intro line under it and the intro alert.',
        }),
        ('Contact details', {
            'fields': ('email', 'phone', 'support_hours'),
            'description': 'Used by the contact cards, the Contact page and the footer.',
        }),
        ('Location & map', {
            'fields': (
                'location_hotel', 'property_name', 'address', 'city', 'state_region',
                'country', 'postal_code', 'latitude', 'longitude', 'map_picker',
            ),
            'description': 'Link a property to publish its name, address and coordinates. '
                           'Otherwise the values below are used for the company office.',
        }),
        ('Primary actions', {
            'fields': ('primary_cta_text', 'primary_cta_link', 'secondary_cta_text', 'secondary_cta_link'),
        }),
        ('Booking support', {
            'fields': (
                'booking_support_enabled', 'booking_support_title', 'booking_support_description',
                'booking_support_button_text', 'booking_support_button_link',
            ),
            'description': 'Point the button at /dashboard/bookings to reuse the existing booking management flow.',
        }),
        ('Guest support', {'fields': ('support_enabled', 'support_title', 'support_description')}),
        ('Contact form', {
            'fields': (
                'contact_form_enabled', 'form_success_message', 'form_error_message',
                'form_name_required', 'form_email_required',
                'form_phone_enabled', 'form_phone_required',
                'form_booking_reference_enabled', 'form_booking_reference_required',
                'form_subject_required', 'form_message_required',
            ),
            'description': 'Submissions are stored here and emailed to the address in '
                           'CONTACT_NOTIFICATION_EMAIL (backend/.env).',
        }),
        ('Sections', {
            'fields': ('cards_enabled', 'map_enabled', 'faq_enabled'),
            'description': 'Turn whole sections of the public Contact page on or off.',
        }),
        ('SEO', {'fields': ('seo_title', 'seo_description')}),
    )

    def has_add_permission(self, request):
        # One global record: the first admin visit creates it through load().
        return not ContactSettings.objects.exists()


@admin.register(ContactCard)
class ContactCardAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'description', 'cta_label', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('kind', 'is_active')
    search_fields = ('title', 'description', 'cta_label')
    fieldsets = (
        ('Card', {'fields': ('kind', 'title', 'description')}),
        ('Link', {
            'fields': ('cta_label', 'icon', 'cta_link'),
            'description': 'The email, phone and location cards take their value from Contact settings; '
                           'only a custom card needs its own link.',
        }),
        ('Display', {'fields': ('order', 'is_active')}),
    )


@admin.register(ContactFaq)
class ContactFaqAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('question', 'answer')
    fieldsets = (
        (None, {'fields': ('question', 'answer')}),
        ('Display', {
            'fields': ('order', 'is_active'),
            'description': 'Published FAQs appear on the Contact page in order.',
        }),
    )


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    """Triage inbox for the public contact form — staff only, no public API."""

    list_display = ('name', 'email', 'phone', 'subject', 'booking_reference', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name', 'email', 'phone', 'subject', 'message', 'booking_reference')
    date_hierarchy = 'created_at'
    list_editable = ('status',)
    readonly_fields = (
        'name', 'email', 'phone', 'booking_reference', 'subject', 'message', 'created_at', 'updated_at',
    )
    fieldsets = (
        ('Message', {
            'fields': ('name', 'email', 'phone', 'booking_reference', 'subject', 'message', 'created_at'),
        }),
        ('Triage', {'fields': ('status', 'updated_at')}),
    )
    actions = ('mark_in_progress', 'mark_resolved', 'mark_archived')

    def has_add_permission(self, request):
        # Messages only ever arrive through the public form.
        return False

    @admin.action(description='Mark selected messages as in progress')
    def mark_in_progress(self, request, queryset):
        updated = queryset.update(status=ContactMessage.Status.IN_PROGRESS)
        self.message_user(request, f'{updated} message(s) marked as in progress.')

    @admin.action(description='Mark selected messages as resolved')
    def mark_resolved(self, request, queryset):
        updated = queryset.update(status=ContactMessage.Status.RESOLVED)
        self.message_user(request, f'{updated} message(s) marked as resolved.')

    @admin.action(description='Archive selected messages')
    def mark_archived(self, request, queryset):
        updated = queryset.update(status=ContactMessage.Status.ARCHIVED)
        self.message_user(request, f'{updated} message(s) archived.')


@admin.register(GalleryImage)
class GalleryImageAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = ('image_preview', 'title', 'section', 'order')
    list_editable = ('order',)
    list_filter = ('section',)
    search_fields = ('title', 'caption')
    autocomplete_fields = ('section',)
