from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User
from core.admin import image_thumbnail


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('avatar_preview', 'username', 'email', 'display_name', 'role', 'phone', 'booking_total', 'is_active')
    list_display_links = ('username',)
    list_filter = ('role', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'phone')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login', 'avatar_display')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'address', 'city', 'country'),
        }),
        ('Avatar', {'fields': ('avatar', 'avatar_url', 'avatar_display')}),
        ('Role & permissions', {
            'fields': ('role', 'marketing_opt_in', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('bookings')

    def avatar_preview(self, obj):
        return image_thumbnail(obj.avatar, obj.avatar_url, 40, 40)

    avatar_preview.short_description = 'Avatar'

    def avatar_display(self, obj):
        return image_thumbnail(obj.avatar, obj.avatar_url, 90, 90)

    avatar_display.short_description = 'Current avatar'

    def booking_total(self, obj):
        return obj.bookings.count()

    booking_total.short_description = 'Bookings'
