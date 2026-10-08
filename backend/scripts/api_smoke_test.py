"""End-to-end smoke test for the SkyStay API.

Runs the full customer journey against a *running* server using only the
standard library, so it works on any machine with Python installed:

    python scripts/api_smoke_test.py
    python scripts/api_smoke_test.py http://127.0.0.1:8000

Exits with status 0 when every check passes, 1 otherwise.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get('SKYSTAY_API', 'http://127.0.0.1:8000')).rstrip('/')

# Seeded demo customers. `seed_data` creates `delyanka`; the account may have
# been renamed from the admin afterwards, so try each until one signs in.
DEMO_CUSTOMERS = ('delyanka', 'priyanka')
DEMO_PASSWORD = 'demo12345'

PASSED = []
FAILED = []


def check(label, condition, detail=''):
    if condition:
        PASSED.append(label)
        print(f'  PASS  {label}')
    else:
        FAILED.append(f'{label} — {detail}')
        print(f'  FAIL  {label}  {detail}')


def call(path, method='GET', body=None, token=None):
    url = f'{BASE}{path}'
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header('Accept', 'application/json')
    if data:
        request.add_header('Content-Type', 'application/json')
    if token:
        request.add_header('Authorization', f'Token {token}')

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read().decode()
            return response.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as error:
        payload = error.read().decode()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = payload
        return error.code, parsed


def main():
    today = date.today()
    check_in = (today + timedelta(days=21)).isoformat()
    check_out = (today + timedelta(days=24)).isoformat()

    print(f'\nSkyStay API smoke test against {BASE}\n')

    print('Public content')
    status, health = call('/api/health/')
    check('health endpoint responds', status == 200 and health.get('database') == 'ok', str(health))

    status, settings = call('/api/settings/')
    check('site settings load', status == 200 and settings.get('site_title'), str(status))
    check('header navigation is populated', len(settings.get('header_links', [])) > 0)

    status, home = call('/api/home/')
    check('homepage payload loads', status == 200)
    check('hero banner published', len(home.get('heroes', [])) > 0)
    check('featured hotels published', len(home.get('featured_hotels', [])) > 0)
    check('homepage text sections published', 'featured_hotels' in home.get('sections', {}))
    check('testimonials published', len(home.get('testimonials', [])) > 0)

    print('\nCatalogue')
    status, hotels = call(f'/api/hotels/?check_in={check_in}&check_out={check_out}')
    check('hotel list is paginated', status == 200 and 'results' in hotels and 'count' in hotels)
    if not hotels.get('results'):
        check('at least one hotel exists', False, 'run `python manage.py seed_data` first')
        return report()

    first = hotels['results'][0]
    check('hotel card exposes rating + price', first.get('rating') is not None and first.get('starting_price'))
    check('hotel card exposes an image url', bool(first.get('image')))

    status, filtered = call('/api/hotels/?search=bali&sort=price_low')
    check('search filter works', status == 200 and 'results' in filtered)

    status, price_filtered = call('/api/hotels/?min_price=100&max_price=160')
    check(
        'price range filter respects bounds',
        status == 200 and all(100 <= float(h['starting_price']) <= 160 for h in price_filtered['results']),
    )

    status, meta = call('/api/hotels/filters/')
    check('filter metadata loads', status == 200 and len(meta.get('locations', [])) > 0)
    check('price range is 2dp formatted', str(meta['price_range']['min']).count('.') == 1, str(meta['price_range']))

    slug = first['slug']
    status, detail = call(f'/api/hotels/{slug}/?check_in={check_in}&check_out={check_out}')
    check('hotel detail loads by slug', status == 200 and detail.get('slug') == slug)
    check('hotel detail includes rooms', len(detail.get('rooms', [])) > 0)
    check('hotel detail includes highlights', len(detail.get('highlights', [])) > 0)

    room = detail['rooms'][0]
    status, quote = call(f"/api/rooms/{room['id']}/availability/?check_in={check_in}&check_out={check_out}&guests=1")
    check('room availability quotes a price', status == 200 and quote.get('is_available') is True, str(quote))
    check('quote reports 3 nights', quote.get('nights') == 3, str(quote.get('nights')))
    expected_subtotal = float(room['price_per_night']) * 3
    check(
        'subtotal matches price x nights',
        abs(float(quote['subtotal']) - expected_subtotal) < 0.01,
        f"{quote.get('subtotal')} vs {expected_subtotal}",
    )

    status, search = call(f'/api/availability/?check_in={check_in}&check_out={check_out}&guests=2')
    check('cross-hotel availability search works', status == 200 and search.get('count', 0) > 0)

    print('\nAuthentication')
    status, login, customer = 0, {}, None
    for candidate in DEMO_CUSTOMERS:
        status, login = call('/api/auth/login/', 'POST', {'username': candidate, 'password': DEMO_PASSWORD})
        if status == 200 and login.get('token'):
            customer = candidate
            break
    check('demo customer can sign in', customer is not None, str(login)[:160])
    if customer is None:
        return report()

    token = login['token']
    status, me = call('/api/auth/me/', token=token)
    check('authenticated profile loads', status == 200 and me.get('username') == customer)

    bad_status, bad_login = call('/api/auth/login/', 'POST', {'username': customer, 'password': 'wrong'})
    check('bad credentials are rejected', bad_status == 400, str(bad_login)[:120])

    print('\nBooking flow')
    status, created = call(
        '/api/bookings/',
        'POST',
        {
            'room': room['id'],
            'check_in': check_in,
            'check_out': check_out,
            'guests': 1,
            'rooms_count': 1,
            'special_requests': 'Smoke test booking — safe to cancel.',
        },
        token=token,
    )
    check('booking is created', status == 201, str(created)[:200])
    if status != 201:
        return report()

    reference = created['reference']
    check('booking reference is generated', reference.startswith('SKY-'), reference)
    check('guest details default to the profile', created.get('guest_email') == me.get('email'))
    check('total price equals subtotal when tax is 0', created['total_price'] == created['subtotal'])

    status, fetched = call(f'/api/bookings/{reference}/', token=token)
    check('booking can be fetched by reference', status == 200 and fetched['reference'] == reference)

    status, summary = call('/api/bookings/summary/', token=token)
    check('dashboard summary loads', status == 200 and 'stats' in summary)
    check('new booking counts as upcoming', len(summary.get('upcoming', [])) >= 1)

    status, cancelled = call(f'/api/bookings/{reference}/cancel/', 'POST', token=token)
    check('booking can be cancelled', status == 200 and cancelled.get('status') == 'cancelled', str(cancelled)[:160])

    status, rebooking = call(
        '/api/bookings/',
        'POST',
        {'room': room['id'], 'check_in': check_in, 'check_out': check_out, 'guests': 1},
        token=token,
    )
    check('cancelling frees the inventory', status == 201, str(rebooking)[:160])
    if status == 201:
        call(f"/api/bookings/{rebooking['reference']}/cancel/", 'POST', token=token)

    print('\nReviews')
    status, reviews = call(f'/api/reviews/?hotel={slug}')
    check('hotel reviews load', status == 200 and 'results' in reviews)
    check('hotel rating aggregate is populated', float(detail.get('rating') or 0) > 0, str(detail.get('rating')))

    print('\nAdmin')
    request = urllib.request.Request(f'{BASE}/admin/login/')
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            check('django admin login page is reachable', response.status == 200)
    except urllib.error.HTTPError as error:  # pragma: no cover
        check('django admin login page is reachable', False, str(error.code))

    return report()


def report():
    print(f'\n{len(PASSED)} passed, {len(FAILED)} failed')
    if FAILED:
        print('\nFailures:')
        for failure in FAILED:
            print(f'  - {failure}')
        return 1
    print('All checks passed.\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
