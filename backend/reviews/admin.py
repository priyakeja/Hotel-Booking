from django.contrib import admin, messages

from reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'author_name', 'rating', 'title', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating', 'hotel')
    search_fields = ('title', 'comment', 'hotel__name', 'user__username', 'user__email')
    autocomplete_fields = ('hotel', 'user', 'booking')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_approved',)
    actions = ('approve_reviews', 'unapprove_reviews')
    fieldsets = (
        (None, {'fields': ('hotel', 'user', 'booking', 'rating', 'title', 'comment')}),
        ('Moderation', {'fields': ('is_approved', 'created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('hotel', 'user')

    @admin.action(description='Approve selected reviews')
    def approve_reviews(self, request, queryset):
        count = 0
        for review in queryset:
            review.is_approved = True
            review.save()
            count += 1
        self.message_user(request, f'{count} review(s) approved.', messages.SUCCESS)

    @admin.action(description='Hide selected reviews')
    def unapprove_reviews(self, request, queryset):
        count = 0
        for review in queryset:
            review.is_approved = False
            review.save()
            count += 1
        self.message_user(request, f'{count} review(s) hidden.', messages.SUCCESS)
