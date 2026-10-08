from django.contrib import admin, messages
from django.utils.html import format_html

from bookings.models import Booking, Payment


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = ('order_id', 'payment_id', 'signature', 'amount', 'currency', 'cash_remaining_display', 'paid_at', 'created_at')
    fields = ('provider', 'order_id', 'payment_id', 'amount', 'cash_received', 'cash_remaining_display', 'status', 'paid_at', 'created_at')

    def cash_remaining_display(self, obj):
        if not obj or not obj.pk:
            return '₹0.00'
        return f'₹{obj.cash_remaining}'

    cash_remaining_display.short_description = 'Cash Remaining'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'guest_name', 'hotel_name', 'room_name', 'check_in', 'check_out',
        'nights', 'guests', 'rooms_count', 'total_price', 'payment_provider_display',
        'status_badge', 'payment_status_badge', 'created_at',
    )
    list_filter = ('status', 'payment_status', 'payment__provider', 'check_in', 'room__hotel')
    search_fields = ('reference', 'guest_name', 'guest_email', 'guest_phone', 'room__name', 'room__hotel__name')
    date_hierarchy = 'check_in'
    autocomplete_fields = ('user', 'room')
    readonly_fields = ('reference', 'nights', 'subtotal', 'tax_amount', 'total_price', 'created_at', 'updated_at')
    inlines = [PaymentInline]
    save_on_top = True
    actions = ('mark_confirmed', 'mark_checked_in', 'mark_completed', 'mark_cancelled')
    fieldsets = (
        ('Reference', {'fields': ('reference', 'user', 'status', 'payment_status', 'created_at', 'updated_at')}),
        ('Stay', {'fields': ('room', 'check_in', 'check_out', 'nights', 'guests', 'rooms_count')}),
        ('Pricing', {'fields': ('price_per_night', 'subtotal', 'tax_amount', 'total_price')}),
        ('Guest details', {'fields': ('guest_name', 'guest_email', 'guest_phone', 'special_requests')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('room', 'room__hotel', 'user', 'payment')

    # -- list columns ----------------------------------------------------
    def hotel_name(self, obj):
        return obj.room.hotel.name

    hotel_name.short_description = 'Hotel'
    hotel_name.admin_order_field = 'room__hotel__name'

    def room_name(self, obj):
        return obj.room.name

    room_name.short_description = 'Room'

    def payment_provider_display(self, obj):
        payment = getattr(obj, 'payment', None)
        if not payment:
            return 'N/A'
        return payment.provider.upper()

    payment_provider_display.short_description = 'Method'

    def status_badge(self, obj):
        colors = {
            Booking.Status.PENDING: '#b45309',
            Booking.Status.CONFIRMED: '#15803d',
            Booking.Status.CHECKED_IN: '#1d4ed8',
            Booking.Status.COMPLETED: '#4b5563',
            Booking.Status.CANCELLED: '#b91c1c',
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;'
            'font-size:11px;white-space:nowrap;">{}</span>',
            colors.get(obj.status, '#4b5563'), obj.get_status_display(),
        )

    status_badge.short_description = 'Status'

    def payment_status_badge(self, obj):
        colors = {
            Booking.PaymentStatus.UNPAID: '#b91c1c',
            Booking.PaymentStatus.PARTIALLY_PAID: '#d97706',
            Booking.PaymentStatus.PAID: '#15803d',
            Booking.PaymentStatus.REFUNDED: '#4b5563',
        }
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;'
            'font-size:11px;white-space:nowrap;">{}</span>',
            colors.get(obj.payment_status, '#4b5563'), obj.get_payment_status_display(),
        )

    payment_status_badge.short_description = 'Payment'

    # -- bulk actions ----------------------------------------------------
    def _bulk_status(self, request, queryset, status, label):
        updated = queryset.update(status=status)
        self.message_user(request, f'{updated} booking(s) marked as {label}.', messages.SUCCESS)

    @admin.action(description='Mark selected bookings as Confirmed')
    def mark_confirmed(self, request, queryset):
        self._bulk_status(request, queryset, Booking.Status.CONFIRMED, 'confirmed')

    @admin.action(description='Mark selected bookings as Checked in')
    def mark_checked_in(self, request, queryset):
        self._bulk_status(request, queryset, Booking.Status.CHECKED_IN, 'checked in')

    @admin.action(description='Mark selected bookings as Completed')
    def mark_completed(self, request, queryset):
        self._bulk_status(request, queryset, Booking.Status.COMPLETED, 'completed')

    @admin.action(description='Cancel selected bookings')
    def mark_cancelled(self, request, queryset):
        self._bulk_status(request, queryset, Booking.Status.CANCELLED, 'cancelled')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'order_id', 'booking', 'provider', 'amount', 'cash_received',
        'cash_remaining_display', 'status', 'paid_at', 'created_at',
    )
    list_filter = ('status', 'provider', 'currency')
    search_fields = ('order_id', 'payment_id', 'booking__reference', 'booking__guest_email')
    readonly_fields = ('cash_remaining_display', 'created_at', 'updated_at')

    def cash_remaining_display(self, obj):
        return f'₹{obj.cash_remaining}'

    cash_remaining_display.short_description = 'Cash Remaining'


