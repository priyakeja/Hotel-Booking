"""Root URL configuration for the SkyStay booking platform."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from core.views import ApiRootView, HealthView

admin.site.site_header = settings.ADMIN_SITE_HEADER
admin.site.site_title = settings.ADMIN_SITE_TITLE
admin.site.index_title = settings.ADMIN_INDEX_TITLE
# "VIEW SITE" must open the React app, not the API-only Django root.
admin.site.site_url = settings.FRONTEND_URL

urlpatterns = [
    path('admin/', admin.site.urls),

    # Landing page for the Django host itself (the React app lives separately).
    path('', TemplateView.as_view(
        template_name='index.html',
        extra_context={'frontend_url': settings.FRONTEND_URL},
    ), name='landing'),

    # Public API
    path('api/', ApiRootView.as_view(), name='api-root'),
    path('api/health/', HealthView.as_view(), name='api-health'),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('content.urls')),
    path('api/', include('hotels.urls')),
    path('api/', include('offers.urls')),
    path('api/', include('bookings.urls')),
    path('api/', include('reviews.urls')),
]

if settings.DEBUG:
    # Serve uploaded logos, banners and galleries during development.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
