from rest_framework import serializers

from core.serializers import ResolvedImageMixin
from reviews.models import Review


class ReviewSerializer(ResolvedImageMixin, serializers.ModelSerializer):
    author_name = serializers.CharField(read_only=True)
    author_avatar = serializers.SerializerMethodField()
    hotel_name = serializers.CharField(source='hotel.name', read_only=True)
    hotel_slug = serializers.CharField(source='hotel.slug', read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'hotel', 'hotel_name', 'hotel_slug', 'booking', 'rating', 'title',
            'comment', 'author_name', 'author_avatar', 'is_approved', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'is_approved', 'author_name']

    def get_author_avatar(self, obj):
        if not obj.user:
            return None
        return self.resolved(obj.user.avatar, obj.user.avatar_url)

    def validate_booking(self, booking):
        if booking and booking.user_id != self.context['request'].user.id:
            raise serializers.ValidationError('You can only review your own bookings.')
        return booking

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Rating must be between 1 and 5.')
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        booking = attrs.get('booking')
        if booking and Review.objects.filter(user=user, booking=booking).exists():
            raise serializers.ValidationError({'booking': 'You already reviewed this stay.'})
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
