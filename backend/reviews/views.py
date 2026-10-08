from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from core.permissions import IsOwnerOrReadOnly
from hotels.models import Hotel
from reviews.models import Review
from reviews.serializers import ReviewSerializer


class ReviewViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        queryset = Review.objects.select_related('user', 'hotel')
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_approved=True)

        hotel = self.request.query_params.get('hotel')
        if hotel:
            # Accept either the slug or the numeric id so the endpoint is easy to consume.
            if str(hotel).isdigit():
                queryset = queryset.filter(hotel_id=hotel)
            else:
                queryset = queryset.filter(hotel__slug=hotel)

        mine = self.request.query_params.get('mine')
        if mine == 'true' and self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def perform_create(self, serializer):
        serializer.save()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        slug = self.request.query_params.get('hotel')
        if slug and not str(slug).isdigit():
            context['hotel'] = Hotel.objects.filter(slug=slug).first()
        return context
