# SkyStay — Dynamic Hotel Booking Platform

A production-shaped hotel booking application where **100% of the content is managed from
the Django admin**. React never hardcodes a headline, a logo, a hotel or a price — the
frontend renders whatever the CMS publishes, through a DRF API on MySQL.

- **Frontend** — React 19 + Vite (JavaScript) with vanilla CSS (design tokens, no framework)
- **Backend** — Python 3.10–3.12, Django 5.0, Django REST Framework, django-cors-headers
- **Database** — MySQL / MariaDB (via `mysqlclient`) — developed against XAMPP's MariaDB 10.4

> Version pins matter here: Django 5.0 is the newest release that still supports MariaDB 10.4,
> which is what XAMPP bundles. Django 5.0 is only supported on Python 3.10–3.12, so build the
> backend virtualenv with a 3.10–3.12 interpreter — a new 3.13/3.14 interpreter will install it
> but is not a supported combination.

---

## 1. What's included

### Guest / customer
- Dynamic homepage: hero banner, search form, trust strip, featured hotels, amenities band,
  testimonials, "why us" band with gallery, closing CTA.
- Hotel listing with search, date range, guest capacity, price range, star rating, room type
  and amenity filters, plus sorting and pagination.
- Hotel detail page with photo lightbox gallery, tabs (Overview / Rooms / Amenities / Reviews),
  highlight list, facilities and guest reviews.
- Live availability checking per room type — real inventory maths, not a static calendar.
- Booking flow with guest details, live price breakdown and instant confirmation reference.
- Dynamic Contact page: intro alert, email/phone/location cards, primary actions, booking
  support band, an interactive OpenStreetMap section with **Get directions**, guest support
  hours, a configurable contact form and a FAQ accordion — every string, the coordinates and
  each section's visibility come from `Admin → Contact page settings`.
- Customer dashboard: stat cards, upcoming stay, booking history, cancel booking, profile
  editing, own reviews.
- Register / login / logout with DRF token authentication.

### Hotel administrator (Django admin as CMS)
Every model below is registered with image previews, inline galleries, filters, search,
`list_editable` fields and bulk status actions.

- **Contact page settings** — one form holding the page title, intro, email, phone, support
  hours, address, latitude/longitude (with a searchable, draggable map picker), primary CTAs,
  booking support, guest support, the contact form's rules/messages, per-section visibility
  toggles and the page's SEO title/description. What is saved here is live on the public page
  immediately — no deploy.
- **Contact cards / Contact FAQs** — reorder, edit, publish or hide each card and FAQ row.
- **Contact messages** — the inbox for form submissions with inline status triage
  (New / In progress / Resolved / Archived) and bulk actions. Never exposed publicly.

---

## 2. Project layout

```
.
├── backend/
│   ├── config/              # settings, root urls, wsgi/asgi
│   ├── core/                # shared abstract models, permissions, pagination, helpers, API root
│   ├── accounts/            # custom User + token auth endpoints
│   ├── content/             # CMS: SiteSettings, NavLink, HeroBanner, Feature, Amenity,
│   │   │                    #      Testimonial, TextSection, GalleryImage, ContactSettings,
│   │   │                    #      ContactCard, ContactFaq, ContactMessage
│   │   └── management/commands/seed_data.py   # demo content seeder
│   ├── hotels/              # Hotel, HotelImage, Room, RoomImage + filtering & availability
│   ├── bookings/            # Booking + reservation lifecycle
│   ├── reviews/             # Review + rating aggregation
│   ├── scripts/api_smoke_test.py              # standalone end-to-end API check
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── api/client.js        # fetch wrapper, token storage, endpoints, error normalisation
    │   ├── context/             # SiteProvider (branding), AuthProvider, ToastProvider
    │   ├── hooks/               # useFetch (abortable), useReveal (scroll animations)
    │   ├── components/          # Navbar, Footer, Hero search, cards, Gallery, Modal, ...
    │   ├── pages/               # Home, Hotels, HotelDetail, Booking, Dashboard, auth, content
    │   ├── styles/              # tokens.css, base.css, components.css, pages.css
    │   └── utils/               # formatting + image helpers
    └── vite.config.js
```

---

## 3. Database design

All models live in `models.py` files; run `python manage.py migrate` to create them.

### `accounts`
| Model | Key fields | Relationships |
|---|---|---|
| `User` (extends `AbstractUser`) | `email` (unique), `role` (`customer`/`hotel_admin`), `phone`, `address`, `city`, `country`, `avatar` (`ImageField`), `avatar_url`, `marketing_opt_in` | `booking_set`, `review_set` (reverse FKs) |

### `content` (the CMS)
| Model | Key fields | Relationships |
|---|---|---|
| `SiteSettings` (singleton) | `site_title`, `tagline`, `logo`, `logo_url`, `favicon`, `footer_text`, `meta_description`, `contact_email/phone`, `address`, social URLs, `currency_code`, `currency_symbol`, `tax_percentage`, check-in/out times | — |
| `NavLink` | `label`, `url`, `location` (`header`/`footer`/`footer_legal`), `order`, `is_active` | — |
| `HeroBanner` | `eyebrow`, `title`, `subtitle`, `description`, `background` (`ImageField`), `background_url`, `overlay_opacity`, CTA text/link (x2), `show_search_form` | — |
| `Feature` | `icon` keyword, `title`, `description`, `order` | — |
| `Amenity` | `name` (unique), `icon` keyword, `show_on_homepage`, `order` | `hotels` (**M2M**), `rooms` (**M2M**) |
| `Testimonial` | `name`, `location`, `message`, `rating`, `avatar`, `order` | `hotel` (**FK → Hotel**, nullable) |
| `TextSection` | `key` (choices), `eyebrow`, `heading`, `subheading`, `body`, `image`, CTA text/link | `gallery` (**reverse FK** ← GalleryImage) |
| `GalleryImage` | `image`, `image_url`, `title`, `caption`, `order` | `section` (**FK → TextSection**) |
| `ContactSettings` (singleton) | `page_title`, `intro_message`, `response_time`, `intro_enabled`, `email`, `phone`, `support_hours`, `property_name`, `address`, `city`, `state_region`, `country`, `postal_code`, `latitude`, `longitude`, `cards_enabled`, `map_enabled`, `booking_support_*`, `support_*`, `contact_form_enabled`, `form_*_required`, `form_success_message`, `form_error_message`, `seo_title`, `seo_description` | `location_hotel` (**FK → Hotel**, nullable) |
| `ContactCard` | `kind` (`email`/`phone`/`location`/`custom`), `title`, `description`, `cta_label`, `icon`, `cta_link`, `order`, `is_active` | — |
| `ContactFaq` | `question`, `answer`, `order`, `is_active` (published) | — |
| `ContactMessage` | `name`, `email`, `booking_reference`, `subject`, `message`, `status` (`new`/`in_progress`/`resolved`/`archived`) | — |

`ContactSettings` is a singleton like `SiteSettings`. Link `location_hotel` to publish a
property's own name/address/coordinates instead of the manual office fields, which keeps
per-property data in one place on a multi-hotel site. Leave it empty for a company-wide
contact page.

### `hotels`
| Model | Key fields | Relationships |
|---|---|---|
| `Hotel` | `name`, `slug` (auto), `city`, `country`, `address`, `short_description`, `description`, `star_rating` (`DecimalField`), `price_per_night` (`DecimalField`), `cover_image`, `cover_image_url`, `highlights`, `latitude/longitude`, `is_featured`, `is_active`, `rating_average`, `review_count` | `amenities` (**M2M → Amenity**), `images` (`HotelImage`), `rooms` (`Room`), `reviews` (`Review`), `testimonials` |
| `HotelImage` | `image`, `image_url`, `caption`, `alt_text`, `order` | `hotel` (**FK → Hotel**) |
| `Room` | `name`, `room_type` (choices), `description`, `price_per_night`, `capacity`, `max_guests`, `bed_type`, `beds`, `size_sqm`, `total_rooms` (inventory), `cover_image`, `cover_image_url`, `is_active`, `order` | `hotel` (**FK**), `amenity_list` (**M2M → Amenity**), `images` (`RoomImage`) |
| `RoomImage` | `image`, `image_url`, `caption`, `order` | `room` (**FK → Room**) |

### `bookings`
| Model | Key fields | Relationships |
|---|---|---|
| `Booking` | `reference` (auto `SKY-XXXXXX`), `check_in`, `check_out`, `nights`, `guests`, `rooms_count`, `price_per_night`, `subtotal`, `tax_amount`, `total_price`, `status`, `special_requests`, `guest_name/email/phone` | `user` (**FK → User**), `room` (**FK → Room**, `PROTECT`) |

Pricing is computed on save from `nights × rooms_count × price_per_night` plus the
`SiteSettings.tax_percentage`. Availability is derived, not stored: a room type is bookable
while `total_rooms − Σ(blocking bookings overlapping the range) > 0`.

### `reviews`
| Model | Key fields | Relationships |
|---|---|---|
| `Review` | `rating` (1–5), `title`, `comment`, `is_approved` | `hotel` (**FK → Hotel**), `user` (**FK → User**), `booking` (**OneToOne → Booking**) |

Saving or deleting a review recalculates `Hotel.rating_average` / `review_count`, so listing
pages never run a per-hotel aggregate query.

---

## 4. Backend setup

### 4.1 Create the MySQL database

With XAMPP, start **MySQL** in the control panel and create the schema from phpMyAdmin
(`http://localhost/phpmyadmin`) or the bundled client:

```bash
C:/xampp/mysql/bin/mysql.exe -u root -e \
  "CREATE DATABASE IF NOT EXISTS skystay_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

On a standalone MySQL server, use a dedicated account instead of `root`:

```sql
CREATE DATABASE IF NOT EXISTS skystay_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'skystay'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON skystay_db.* TO 'skystay'@'localhost';
FLUSH PRIVILEGES;
```

> `mysqlclient` needs MySQL client headers to build. On Windows install the MySQL Connector/C
> or use the prebuilt wheel; on Debian/Ubuntu: `sudo apt install python3-dev default-libmysqlclient-dev build-essential`.

### 4.2 Configure environment

```bash
cd backend
cp .env.example .env      # then edit the DB_* values
```

`config/settings.py` reads MySQL config from `.env`, falling back to
`skystay_db` / `root` / `127.0.0.1:3306` when a key is absent. XAMPP's default `root` user has an
empty password, so `DB_USER=root` with `DB_PASSWORD=` is what a stock XAMPP install needs.

`FRONTEND_URL` in the same file tells Django where the React app lives (default
`http://localhost:5173`). It is what the admin's **VIEW SITE** link opens and what the backend
landing page at `/` links to.

Verify the connection before running migrations — this is the step that fails first when the
server is down or the credentials are wrong:

```bash
cd backend
python manage.py check --database default   # reports a clear error if MySQL is unreachable
python manage.py migrate
```

The MySQL error number in the traceback tells you which piece is wrong:

| Error | Message | Fix |
|---|---|---|
| `2002` / `2003` | `Can't connect to server on '127.0.0.1'` (`Connection refused` on macOS/Linux) | MySQL isn't running — start it in the XAMPP control panel |
| `1045` | `Access denied for user 'root'@'localhost'` | the `DB_USER` / `DB_PASSWORD` pair in `.env` is wrong |
| `1049` | `Unknown database 'skystay_db'` | step 4.1 was skipped — create the schema |

### 4.3 Install, migrate, seed, run

```bash
cd backend
python -m venv venv
venv/Scripts/activate            # Windows;  source venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_data       # demo branding, 6 hotels, 13 rooms, bookings, reviews
python manage.py createsuperuser # (optional — the seeder already creates `admin`)
python manage.py runserver
```

The admin is at **http://127.0.0.1:8000/admin/**. The backend root, **http://127.0.0.1:8000/**,
serves a small landing page linking to the React app, the admin and the API — the Django server
does not render the customer-facing site itself, so open the frontend on its own port (`:5173`).
Clicking **VIEW SITE** in the admin header opens `FRONTEND_URL` directly.

`seed_data` is idempotent — re-run it any time; add `--flush` to reset the demo content first.
Demo logins it creates:

| Role | Username | Password |
|---|---|---|
| Hotel administrator | `admin` | `admin12345` |
| Customer | `delyanka` | `demo12345` |

> Change the admin password before deploying anything.

### 4.4 Email notifications

Reservation email goes out over SMTP. The keys live in `backend/.env`:

| Key | Purpose | Gmail example |
|---|---|---|
| `EMAIL_HOST` / `EMAIL_PORT` | SMTP server | `smtp.gmail.com` / `587` |
| `EMAIL_USE_TLS` | STARTTLS | `True` |
| `EMAIL_HOST_USER` | Sending mailbox | `you@gmail.com` |
| `EMAIL_HOST_PASSWORD` | **App password**, never the account password | 16 characters |
| `DEFAULT_FROM_EMAIL` | "From" header | `SkyStay <you@gmail.com>` |
| `BOOKING_NOTIFICATION_EMAIL` | Receives new-booking notices; defaults to `EMAIL_HOST_USER` | `you@gmail.com` |

Gmail app passwords require 2-Step Verification (Google Account → Security → App passwords).
Google displays them in four groups of four characters; the spaces are stripped for you, so paste
the value as-is.

Three messages are sent:

- **Booking confirmed** to the guest when a reservation is created,
- **Booking cancelled** to the guest when it is cancelled,
- **New booking notice** to `BOOKING_NOTIFICATION_EMAIL` so the front desk can confirm it.

The mails are rendered from `backend/templates/emails/` and pull branding, currency and contact
details from **Site settings**, so editing them in the admin changes the emails too. A failing
mail server is logged and swallowed — a booking is never lost because SMTP is down. Leave
`EMAIL_HOST_USER` empty and Django prints the mails to the console instead, which keeps a fresh
checkout zero-config.

### 4.5 Media files

Uploaded logos, banners and galleries are written to `MEDIA_ROOT` (default `backend/media/`)
and served at `MEDIA_URL` (default `/media/`) in development. In production, serve
`MEDIA_ROOT` from your web server or object storage and set `DJANGO_DEBUG=False`
plus a real `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`.

---

## 5. Frontend setup

```bash
cd frontend
npm install
cp .env.example .env       # VITE_API_URL=http://127.0.0.1:8000/api
npm run dev                # http://127.0.0.1:5173
npm run build              # production bundle in dist/
npm run preview            # serve the built bundle on :4173
```

`CORS_ALLOWED_ORIGINS` in `backend/.env` must include the origin you run the frontend on
(`http://localhost:5173` and `http://127.0.0.1:5173` are configured by default).

---

## 6. API reference

`GET /api/` returns a browsable index of every endpoint.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health/` | API + database health probe |
| GET | `/api/settings/` | Branding, contact details, grouped nav links |
| GET | `/api/home/` | One call that hydrates the entire homepage |
| GET | `/api/contact/` | Contact page payload: settings (location resolved), cards, published FAQs — shared by the Contact page and the footer |
| POST | `/api/contact/messages/` | Submit the public contact form (validation follows the admin's form settings) |
| GET | `/api/sections/<key>/` | A single CMS text section |
| GET | `/api/amenities/` | Amenities (`?homepage=true` filters the homepage set) |
| GET | `/api/hotels/` | Paginated catalogue — `search`, `city`, `min_price`, `max_price`, `star_rating`, `amenity` (repeatable), `room_type`, `guests`, `check_in`, `check_out`, `sort`, `page` |
| GET | `/api/hotels/filters/` | Filter sidebar metadata (locations, price bounds, amenities) |
| GET | `/api/hotels/<slug>/` | Detail incl. gallery, highlights, rooms |
| GET | `/api/hotels/<slug>/availability/` | Per-room availability for a date range |
| GET | `/api/rooms/<id>/availability/` | Quote: availability, nights, subtotal, tax, total |
| GET | `/api/availability/` | Cross-hotel availability search |
| POST/GET | `/api/bookings/` | Create a booking / list your bookings |
| GET/PATCH | `/api/bookings/<reference>/` | Booking detail / edit special requests |
| POST | `/api/bookings/<reference>/cancel/` | Cancel a booking |
| GET | `/api/bookings/summary/` | Dashboard counters + upcoming/recent stays |
| GET/POST | `/api/reviews/?hotel=<slug>` | List / create hotel reviews |
| POST | `/api/auth/register/`, `/api/auth/login/` | Obtain a token |
| POST | `/api/auth/logout/` | Revoke the token |
| GET/PATCH | `/api/auth/me/` | Current profile |

Authenticated requests use `Authorization: Token <key>`.

---

## 7. Managing content from the admin

The Django admin is the CMS. Everything the site shows can be changed without a deploy:

| Admin section | Controls |
|---|---|
| **Contact page settings** | Page title, intro, email, phone, support hours, address, map coordinates (interactive picker), CTAs, booking/guest support, contact form rules and messages, section visibility, SEO |
| **Contact cards / FAQs** | Card titles, descriptions, CTA labels, visibility; FAQ questions, answers, order and publishing |
| **Contact messages** | Read form submissions and triage them (New / In progress / Resolved / Archived) |
| **Site settings** | Site title, tagline, logo, favicon, footer text, contact details, socials, currency, tax |
| **Navigation links** | Header / footer / legal menus, order, visibility |
| **Hero banners** | Homepage background image, overlay strength, copy and CTA buttons |
| **Features** | The trust strip under the hero |
| **Amenities** | Icon keyword + which appear on the homepage and on hotels/rooms |
| **Text sections** | Section headings, about band, CTA band, page copy, image galleries |
| **Testimonials** | Guest quotes with avatar, rating and linked hotel |
| **Hotels / Rooms** | Full CRUD with inline image galleries, amenities, pricing and inventory |
| **Bookings** | Reservations with bulk confirm / check-in / complete / cancel actions |
| **Reviews** | Moderation (approve/hide) — ratings recalculate automatically |

Images accept an **uploaded file** or an **external URL**; uploads always take priority. That is
why the seeder can populate a fully illustrated site while you still replace every image with
your own uploads.

### Contact page data flow

```
Admin → Contact page settings
        │
        ▼
  ContactSettings (database)
        │   GET /api/contact/   (one shared payload)
        ▼
  Contact page  +  Footer contact block
```

The footer reads the same `ContactSettings` record as the Contact page (falling back to
**Site settings** only for a field the admin has left blank), so editing the phone number once
updates both. The map, **View on map** and **Get directions** links are all built from the saved
latitude/longitude by `frontend/src/utils/maps.js` — there are no coordinates in the code.

---

## 8. Verification

```bash
# Backend: 83 tests (auth, CMS, contact page + form, admin screens, filtering,
#           availability, booking, reviews)
cd backend && python manage.py test

# End-to-end API walk-through against a running server
cd backend && python manage.py runserver     # in one shell
python scripts/api_smoke_test.py             # in another

# Frontend production build
cd frontend && npm run build
```

---

## 9. Notes & next steps

- Availability is computed from booking rows at request time — correct and simple. For very
  high traffic, add a nightly materialised calendar table and read from it.
- `ContactSettings` and `SiteSettings` are cached for 10 minutes; saving either one from the
  admin invalidates the cache in the same request, so a saved contact change is live on the
  next page load without a deploy or restart.
- Bookings are confirmed instantly (status `pending` → staff confirms in the admin). No payment
  gateway is wired in; add Stripe at the booking step when you are ready.
- `Booking.rooms_count` lets one reservation hold several identical rooms; inventory accounts
  for it.
- Set `DJANGO_DEBUG=False`, a strong `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and serve
  static/media through your web server before going live.
