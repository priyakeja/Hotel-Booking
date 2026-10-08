from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class ApiRootView(APIView):
    """Human readable index of every public endpoint."""

    permission_classes = [AllowAny]

    def get(self, request):
        base = request.build_absolute_uri('/api/')
        return Response(
            {
                'site': {
                    'settings': f'{base}settings/',
                    'home': f'{base}home/',
                    'contact': f'{base}contact/',
                    'contact_form': f'{base}contact/messages/',
                    'nav_links': f'{base}nav-links/',
                    'amenities': f'{base}amenities/',
                    'testimonials': f'{base}testimonials/',
                    'sections': f'{base}sections/',
                },
                'catalogue': {
                    'hotels': f'{base}hotels/',
                    'hotel_detail': f'{base}hotels/<slug>/',
                    'hotel_filters': f'{base}hotels/filters/',
                    'rooms': f'{base}rooms/',
                    'room_availability': f'{base}rooms/<id>/availability/?check_in=&check_out=',
                    'availability_search': f'{base}availability/?check_in=&check_out=&guests=',
                },
                'bookings': {
                    'create_or_list': f'{base}bookings/',
                    'detail': f'{base}bookings/<reference>/',
                    'dashboard_summary': f'{base}bookings/summary/',
                },
                'auth': {
                    'register': f'{base}auth/register/',
                    'login': f'{base}auth/login/',
                    'logout': f'{base}auth/logout/',
                    'me': f'{base}auth/me/',
                },
                'reviews': f'{base}reviews/?hotel=<slug>',
                'admin': request.build_absolute_uri('/admin/'),
            }
        )


class HealthView(APIView):
    """Confirms the API and, when reachable, the database are up."""

    permission_classes = [AllowAny]

    def get(self, request):
        database = 'unavailable'
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            database = 'ok'
        except Exception as exc:  # noqa: BLE001 - report the error instead of crashing
            database = f'error: {exc.__class__.__name__}'
        return Response({'status': 'ok', 'database': database})
