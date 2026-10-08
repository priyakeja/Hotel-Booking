"""Django admin for the offers / promotions system.

The admin is the single source of truth: create, price, schedule, feature and
disable offers here and the public API reflects it immediately.
"""

from django.contrib import admin, messages
from django.utils.html import format_html

from core.admin import ImagePreviewAdminMixin, SingletonAdmin, image_thumbnail
from offers.models import Offer, OfferBenefit, OfferCategory, OfferImage, OfferSettings


@admin.register(OfferSettings)
class OfferSettingsAdmin(SingletonAdmin):
    save_on_top = True
    fieldsets = (
        ('Page header', {
            'fields': ('page_title', 'page_description'),
            'description': 'The heading and intro shown at the top of the public Offers page.',
        }),
        ('Hero', {
            'fields': ('hero_enabled', 'hero_image', 'hero_image_url', 'hero_search_enabled'),
        }),
        ('Section headings', {
            'fields': (
                'featured_enabled', 'featured_heading', 'featured_subheading',
                'limited_enabled', 'limited_heading', 'limited_subheading', 'limited_window_days',
            ),
        }),
        ('SEO', {'fields': ('seo_title', 'seo_description')}),
    )

    def has_add_permission(self, request):
        return not OfferSettings.objects.exists()


@admin.register(OfferCategory)
class OfferCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'offer_total', 'order', 'is_active')
    list_display_links = ('name',)
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}

    def offer_total(self, obj):
        return obj.offers.count()

    offer_total.short_description = 'Offers'


class OfferBenefitInline(admin.TabularInline):
    model = OfferBenefit
    extra = 2
    fields = ('text', 'icon', 'order', 'is_active')
    ordering = ('order',)


class OfferImageInline(admin.TabularInline):
    model = OfferImage
    extra = 1
    fields = ('image', 'image_url', 'caption', 'alt_text', 'order')
    ordering = ('order',)


@admin.register(Offer)
class OfferAdmin(ImagePreviewAdminMixin, admin.ModelAdmin):
    list_display = (
        'cover_preview', 'title', 'hotel', 'offer_type', 'discount_summary',
        'original_display', 'offer_display', 'start_date', 'end_date',
        'status_badge', 'is_featured', 'is_published',
    )
    list_display_links = ('title',)
    list_editable = ('is_featured', 'is_published')
    list_filter = (
        'is_published', 'is_featured', 'is_disabled',
        'offer_type', 'discount_type', 'category', 'hotel',
    )
    search_fields = ('title', 'short_description', 'description', 'promo_code', 'hotel__name', 'slug')
    autocomplete_fields = ('hotel',)
    filter_horizontal = ('rooms',)
    prepopulated_fields = {'slug': ('title',)}
    inlines = [OfferBenefitInline, OfferImageInline]
    save_on_top = True
    date_hierarchy = 'start_date'
    actions = ('make_published', 'make_draft', 'make_featured', 'remove_featured', 'disable_offers', 'duplicate_offers')
    fieldsets = (
        ('Basic information', {
            'fields': ('title', 'slug', 'short_description', 'description', 'category', 'offer_type'),
        }),
        ('Hotel & rooms', {
            'fields': ('hotel', 'rooms'),
            'description': 'Leave rooms empty to apply the offer to every eligible room in the hotel.',
        }),
        ('Pricing & discount', {
            'fields': ('discount_type', 'discount_value', 'free_nights', 'original_price'),
            'description': 'The offer price is calculated from the discount type and the room rate. '
                           'Set “Original price” only to override the displayed “was” price.',
        }),
        ('Validity', {'fields': ('start_date', 'end_date')}),
        ('Restrictions', {
            'fields': ('min_stay', 'max_stay', 'min_booking_amount', 'blackout_start', 'blackout_end'),
        }),
        ('Promo', {'fields': ('promo_code_enabled', 'promo_code')}),
        ('Terms', {'fields': ('terms',), 'description': 'One term per line.'}),
        ('Media', {'fields': ('image', 'image_url')}),
        ('Publishing', {'fields': ('is_published', 'is_featured', 'is_disabled', 'display_order')}),
        ('Performance', {
            'fields': ('view_count', 'click_count', 'booking_count'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('view_count', 'click_count', 'booking_count')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('hotel').prefetch_related('benefits', 'images', 'rooms')

    # -- list helpers -----------------------------------------------------
    def discount_summary(self, obj):
        return obj.get_discount_type_display()

    discount_summary.short_description = 'Type'

    def original_display(self, obj):
        return f'₹{obj.base_price:.2f}'

    original_display.short_description = 'Original'

    def offer_display(self, obj):
        return f'₹{obj.offer_price:.2f}'

    offer_display.short_description = 'Offer price'

    def status_badge(self, obj):
        colours = {
            Offer.Status.ACTIVE: ('#15803d', '#dcfce7'),
            Offer.Status.SCHEDULED: ('#1d4ed8', '#dbeafe'),
            Offer.Status.EXPIRED: ('#92400e', '#fef3c7'),
            Offer.Status.DISABLED: ('#991b1b', '#fee2e2'),
            Offer.Status.DRAFT: ('#475569', '#e2e8f0'),
        }
        fg, bg = colours.get(obj.status, ('#475569', '#e2e8f0'))
        return format_html(
            '<span style="padding:2px 8px;border-radius:10px;font-weight:600;'
            'background:{};color:{};">{}</span>',
            bg, fg, obj.status_label,
        )

    status_badge.short_description = 'Status'

    # -- actions ----------------------------------------------------------
    @admin.action(description='Publish selected offers')
    def make_published(self, request, queryset):
        updated = queryset.update(is_published=True, is_disabled=False)
        self.message_user(request, f'{updated} offer(s) published.', messages.SUCCESS)

    @admin.action(description='Move selected offers to draft')
    def make_draft(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} offer(s) moved to draft.', messages.SUCCESS)

    @admin.action(description='Feature selected offers')
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} offer(s) featured.', messages.SUCCESS)

    @admin.action(description='Remove featured flag')
    def remove_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} offer(s) unfeatured.', messages.SUCCESS)

    @admin.action(description='Disable selected offers')
    def disable_offers(self, request, queryset):
        updated = queryset.update(is_disabled=True)
        self.message_user(request, f'{updated} offer(s) disabled.', messages.SUCCESS)

    @admin.action(description='Duplicate selected offers')
    def duplicate_offers(self, request, queryset):
        created = 0
        for offer in queryset.prefetch_related('benefits', 'images', 'rooms'):
            benefit_rows = list(offer.benefits.all())
            image_rows = list(offer.images.all())
            room_ids = list(offer.rooms.values_list('id', flat=True))
            offer.pk = None
            offer.slug = ''
            offer.title = f'{offer.title} (copy)'
            offer.is_published = False
            offer.is_featured = False
            offer.save()
            offer.rooms.set(room_ids)
            for benefit in benefit_rows:
                OfferBenefit.objects.create(offer=offer, text=benefit.text, icon=benefit.icon, order=benefit.order, is_active=benefit.is_active)
            for image in image_rows:
                OfferImage.objects.create(offer=offer, image=image.image, image_url=image.image_url, caption=image.caption, alt_text=image.alt_text, order=image.order)
            created += 1
        self.message_user(request, f'{created} offer(s) duplicated.', messages.SUCCESS)

    def cover_preview(self, obj):
        return image_thumbnail(obj.image, obj.image_url, 44, 66)

    cover_preview.short_description = 'Image'
