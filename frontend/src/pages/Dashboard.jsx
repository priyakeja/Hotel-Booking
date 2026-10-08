import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { api } from '../api/client'
import Icon from '../components/Icon'
import { Loader } from '../components/Loader'
import Reveal from '../components/Reveal'
import StarRating from '../components/StarRating'
import { useAuth } from '../context/AuthContext'
import { useSite } from '../context/SiteContext'
import { useToast } from '../context/ToastContext'
import useFetch from '../hooks/useFetch'
import { formatDate, formatMoney, initials, pluralise, statusTone } from '../utils/format'

// [key, label, icon, route] — each dashboard panel is a real, linkable route.
const NAV = [
  ['overview', 'Dashboard', 'grid', '/dashboard'],
  ['bookings', 'My Bookings', 'calendar-check', '/dashboard/bookings'],
  ['profile', 'Profile', 'user', '/dashboard/profile'],
  ['reviews', 'Reviews', 'star', '/dashboard/reviews'],
]

/** Maps a payment status to a badge modifier (kept separate from booking status). */
function paymentTone(status) {
  switch (status) {
    case 'paid':
      return 'success'
    case 'partially_paid':
      return 'info'
    case 'refunded':
      return 'navy'
    case 'unpaid':
    default:
      return 'warning'
  }
}

function PaymentBadge({ booking, label = true }) {
  return (
    <span className={`badge badge--${paymentTone(booking.payment_status)}`}>
      {label ? 'Payment: ' : ''}
      {booking.payment_status_display || 'Unpaid'}
    </span>
  )
}

function ErrorPanel({ onRetry }) {
  return (
    <div className="panel">
      <div className="empty">
        <Icon name="info" size={30} className="empty__icon" />
        <h3>Unable to load your dashboard</h3>
        <p className="tiny">We couldn&apos;t reach your booking data just now. Please try again.</p>
        <button type="button" className="btn btn--gold btn--sm" onClick={onRetry}>
          Try Again
        </button>
      </div>
    </div>
  )
}

/** One reservation, rendered from real booking data. */
function StayCard({ booking, currency, children }) {
  const room = booking.room_detail || {}
  const image = room.hotel_image || room.room_image

  return (
    <div className="stay-card">
      <div className="stay-card__media">
        {image ? (
          <img src={image} alt={room.name || 'Room'} loading="lazy" />
        ) : (
          <span className="stay-card__placeholder">
            <Icon name="building" size={26} />
          </span>
        )}
      </div>

      <div className="stay-card__body">
        <h4 className="stay-card__title">{room.hotel_name}</h4>
        <span className="muted tiny">
          {room.name} · <strong>{booking.reference}</strong>
        </span>
        <div className="stay-card__meta">
          <span>
            <Icon name="calendar" size={12} />
            {formatDate(booking.check_in)} → {formatDate(booking.check_out)}
          </span>
          <span>
            <Icon name="users" size={12} />
            {pluralise(booking.guests, 'guest')}
          </span>
          <span>
            <Icon name="clock" size={12} />
            {pluralise(booking.nights, 'night')}
          </span>
        </div>
      </div>

      <div className="stay-card__actions">
        <span className={`badge badge--${statusTone(booking.status)}`}>{booking.status_display}</span>
        <PaymentBadge booking={booking} />
        <span className="price__amount stay-card__price">{formatMoney(booking.total_price, currency)}</span>
        <Link to={`/dashboard/bookings/${booking.reference}`} className="btn btn--gold btn--sm">
          View Booking
        </Link>
        {children}
      </div>
    </div>
  )
}

/** The "My Bookings" panel: the signed-in customer's full reservation list. */
function MyBookings({ currency }) {
  const toast = useToast()
  const [busyRef, setBusyRef] = useState(null)
  const { data, loading, error, reload } = useFetch(
    (signal) => api.bookings.list({ page_size: 100 }, { signal }),
    [],
  )
  const bookings = data?.results || data || []

  const cancelBooking = async (reference) => {
    setBusyRef(reference)
    try {
      await api.bookings.cancel(reference)
      toast.success(`Booking ${reference} cancelled.`)
      reload()
    } catch (cancelError) {
      toast.error(cancelError.message)
    } finally {
      setBusyRef(null)
    }
  }

  if (loading) {
    return (
      <div className="panel">
        <Loader label="Loading your bookings…" />
      </div>
    )
  }

  if (error) return <ErrorPanel onRetry={reload} />

  return (
    <div className="panel">
      <h3 className="panel__title">My Bookings</h3>
      {bookings.length ? (
        <div className="stack" style={{ gap: 'var(--space-4)' }}>
          {bookings.map((booking) => (
            <StayCard key={booking.reference} booking={booking} currency={currency}>
              {booking.can_be_cancelled ? (
                <button
                  type="button"
                  className="btn btn--outline btn--sm"
                  onClick={() => cancelBooking(booking.reference)}
                  disabled={busyRef === booking.reference}
                >
                  {busyRef === booking.reference ? 'Cancelling…' : 'Cancel'}
                </button>
              ) : null}
            </StayCard>
          ))}
        </div>
      ) : (
        <div className="empty">
          <Icon name="calendar-check" size={28} className="empty__icon" />
          <h3>No Bookings Yet</h3>
          <p className="tiny">Your booking history will appear here once you make a reservation.</p>
          <Link to="/hotels" className="btn btn--gold btn--sm">
            Explore Hotels
          </Link>
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const { user, updateProfile } = useAuth()
  const { currency } = useSite()
  const toast = useToast()
  const location = useLocation()
  const path = location.pathname.replace(/\/+$/, '') || '/'
  const section = NAV.find(([, , , route]) => route === path)?.[0] || 'overview'

  const { data: summary, loading, error, reload } = useFetch((signal) => api.bookings.summary({ signal }), [])
  const { data: myReviews } = useFetch((signal) => api.reviews.list({ mine: 'true' }, { signal }), [])
  const { data: dashboardSection } = useFetch((signal) => api.site.section('dashboard', { signal }), [])

  const [profile, setProfile] = useState({
    first_name: user?.first_name || '',
    last_name: user?.last_name || '',
    phone: user?.phone || '',
    city: user?.city || '',
    country: user?.country || '',
    address: user?.address || '',
  })
  const [savingProfile, setSavingProfile] = useState(false)

  // Completion is derived from the saved (authenticated) user record, so it
  // reflects what is actually stored — not just what is typed in the form.
  const PROFILE_FIELDS = ['first_name', 'last_name', 'phone', 'city', 'country', 'address']
  const completedFields = PROFILE_FIELDS.filter((key) => String(user?.[key] || '').trim()).length
  const completionPercent = Math.round((completedFields / PROFILE_FIELDS.length) * 100)

  const stats = summary?.stats || {}
  const upcoming = summary?.upcoming || []
  const recent = summary?.recent || []
  const reviews = myReviews?.results || myReviews || []

  const saveProfile = async (event) => {
    event.preventDefault()
    setSavingProfile(true)
    try {
      await updateProfile(profile)
      toast.success('Profile updated successfully.')
    } catch (saveError) {
      toast.error(saveError.message)
    } finally {
      setSavingProfile(false)
    }
  }

  return (
    <>
      <section className="page-hero" style={{ paddingBottom: 'var(--space-7)' }}>
        <div className="container">
          <div className="breadcrumb">
            <Link to="/">Home</Link>
            <span className="breadcrumb__sep">/</span>
            <span>Dashboard</span>
          </div>
          <h1>{dashboardSection?.heading || 'My Dashboard'}</h1>
          <p>
            {dashboardSection?.subheading || `Welcome back, ${user?.first_name || user?.display_name || 'traveller'}.`}{' '}
            Track your stays and manage your bookings.
          </p>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="container">
          <div className="dashboard">
            {/* --- sidebar -------------------------------------------- */}
            <aside className="dash-nav">
              <div className="dash-nav__user">
                {user?.avatar_display ? (
                  <img className="dash-nav__avatar" src={user.avatar_display} alt="" />
                ) : (
                  <span className="dash-nav__avatar dash-nav__avatar--fallback">
                    {initials(user?.display_name || user?.username) || 'U'}
                  </span>
                )}
                <div>
                  <div className="dash-nav__name">{user?.display_name || user?.username}</div>
                  <div className="dash-nav__email">{user?.email}</div>
                </div>
              </div>

              <nav className="dash-nav__links">
                {NAV.map(([value, label, icon, route]) => (
                  <Link
                    key={value}
                    to={route}
                    className={`dash-nav__link ${section === value ? 'is-active' : ''}`.trim()}
                  >
                    <Icon name={icon} size={16} />
                    {label}
                  </Link>
                ))}
              </nav>
            </aside>

            {/* --- content -------------------------------------------- */}
            <div>
              {section === 'overview' ? (
                loading ? (
                  <Loader label="Loading your dashboard…" />
                ) : error ? (
                  <ErrorPanel onRetry={reload} />
                ) : (
                  <>
                    <div className="stat-grid">
                      <Reveal>
                        <div className="stat">
                          <div className="stat__label">Total Bookings</div>
                          <div className="stat__value">{stats.total_bookings ?? 0}</div>
                          <span className="stat__foot">
                            <Icon name="trending-up" size={13} /> Lifetime reservations
                          </span>
                        </div>
                      </Reveal>
                      <Reveal delay={80}>
                        <div className="stat">
                          <div className="stat__label">Upcoming Stays</div>
                          <div className="stat__value">{stats.upcoming_stays ?? 0}</div>
                          <span className="stat__foot">
                            <Icon name="calendar" size={13} /> Active future bookings
                          </span>
                        </div>
                      </Reveal>
                      <Reveal delay={160}>
                        <div className="stat">
                          <div className="stat__label">Past Stays</div>
                          <div className="stat__value">{stats.past_stays ?? 0}</div>
                          <span className="stat__foot">
                            <Icon name="award" size={13} /> Completed &amp; past stays
                          </span>
                        </div>
                      </Reveal>
                      <Reveal delay={240}>
                        <div className="stat">
                          <div className="stat__label">Total Spent</div>
                          <div className="stat__value">{formatMoney(stats.total_spend, currency)}</div>
                          <span className="stat__foot">
                            <Icon name="wallet" size={13} /> Amount received
                          </span>
                        </div>
                      </Reveal>
                    </div>

                    <div className="panel" style={{ marginTop: 'var(--space-5)' }}>
                      <div className="row-between" style={{ marginBottom: 'var(--space-4)' }}>
                        <h3 className="panel__title" style={{ margin: 0 }}>
                          Upcoming Stays
                        </h3>
                        <Link to="/dashboard/bookings" className="btn btn--ghost btn--sm">
                          View all
                        </Link>
                      </div>

                      {upcoming.length ? (
                        <div className="stack" style={{ gap: 'var(--space-4)' }}>
                          {upcoming.map((booking) => (
                            <StayCard key={booking.reference} booking={booking} currency={currency} />
                          ))}
                        </div>
                      ) : (
                        <div className="empty">
                          <Icon name="calendar" size={28} className="empty__icon" />
                          <h3>No Upcoming Stays</h3>
                          <p className="tiny">You don&apos;t have any upcoming hotel stays.</p>
                          <Link to="/hotels" className="btn btn--gold btn--sm">
                            Explore Hotels
                          </Link>
                        </div>
                      )}
                    </div>

                    <div className="panel">
                      <h3 className="panel__title">Recent Bookings</h3>
                      {recent.length ? (
                        <div className="table-wrap">
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Hotel</th>
                                <th>Room</th>
                                <th>Check-in → Check-out</th>
                                <th>Booking Status</th>
                                <th>Payment Status</th>
                                <th>Total</th>
                                <th>Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {recent.map((booking) => (
                                <tr key={booking.reference}>
                                  <td>
                                    <strong>{booking.room_detail?.hotel_name}</strong>
                                    <div className="tiny muted">{booking.reference}</div>
                                  </td>
                                  <td>{booking.room_detail?.name}</td>
                                  <td className="nowrap">
                                    {formatDate(booking.check_in)} → {formatDate(booking.check_out)}
                                  </td>
                                  <td>
                                    <span className={`badge badge--${statusTone(booking.status)}`}>
                                      {booking.status_display}
                                    </span>
                                  </td>
                                  <td>
                                    <PaymentBadge booking={booking} label={false} />
                                  </td>
                                  <td>{formatMoney(booking.total_price, currency)}</td>
                                  <td>
                                    <Link
                                      to={`/dashboard/bookings/${booking.reference}`}
                                      className="btn btn--ghost btn--sm"
                                    >
                                      View
                                    </Link>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="empty">
                          <Icon name="calendar-check" size={28} className="empty__icon" />
                          <h3>{stats.total_bookings ? 'No past bookings yet' : 'No Bookings Yet'}</h3>
                          <p className="tiny">
                            {stats.total_bookings
                              ? 'Your past stays will appear here after you check out.'
                              : 'Your booking history will appear here once you make a reservation.'}
                          </p>
                          <Link to="/hotels" className="btn btn--gold btn--sm">
                            Explore Hotels
                          </Link>
                        </div>
                      )}
                    </div>
                  </>
                )
              ) : null}

              {section === 'bookings' ? <MyBookings currency={currency} /> : null}

              {section === 'profile' ? (
                <div className="panel">
                  <div className="row-between" style={{ marginBottom: 'var(--space-4)' }}>
                    <h3 className="panel__title" style={{ margin: 0 }}>
                      Profile
                    </h3>
                    <span className="muted tiny">Profile completed: {completionPercent}%</span>
                  </div>
                  <form onSubmit={saveProfile}>
                    <div className="profile-grid">
                      <label className="field">
                        <span className="field__label">First name</span>
                        <input
                          className="input"
                          value={profile.first_name}
                          onChange={(event) => setProfile((c) => ({ ...c, first_name: event.target.value }))}
                        />
                      </label>
                      <label className="field">
                        <span className="field__label">Last name</span>
                        <input
                          className="input"
                          value={profile.last_name}
                          onChange={(event) => setProfile((c) => ({ ...c, last_name: event.target.value }))}
                        />
                      </label>
                      <label className="field">
                        <span className="field__label">Phone</span>
                        <input
                          className="input"
                          value={profile.phone}
                          onChange={(event) => setProfile((c) => ({ ...c, phone: event.target.value }))}
                        />
                      </label>
                      <label className="field">
                        <span className="field__label">City</span>
                        <input
                          className="input"
                          value={profile.city}
                          onChange={(event) => setProfile((c) => ({ ...c, city: event.target.value }))}
                        />
                      </label>
                      <label className="field">
                        <span className="field__label">Country</span>
                        <input
                          className="input"
                          value={profile.country}
                          onChange={(event) => setProfile((c) => ({ ...c, country: event.target.value }))}
                        />
                      </label>
                      <label className="field">
                        <span className="field__label">Address</span>
                        <input
                          className="input"
                          value={profile.address}
                          onChange={(event) => setProfile((c) => ({ ...c, address: event.target.value }))}
                        />
                      </label>
                    </div>

                    <label className="field">
                      <span className="field__label">Email</span>
                      <input className="input" value={user?.email || ''} disabled />
                      <span className="field__hint">Contact support to change the email on your account.</span>
                    </label>

                    <button type="submit" className="btn btn--gold" disabled={savingProfile}>
                      {savingProfile ? 'Saving…' : 'Save changes'}
                    </button>
                  </form>
                </div>
              ) : null}

              {section === 'reviews' ? (
                <div className="panel">
                  <h3 className="panel__title">My reviews</h3>
                  {reviews.length ? (
                    <div className="review-list">
                      {reviews.map((review) => (
                        <article key={review.id} className="review">
                          <div className="review__head">
                            <div>
                              <div className="review__name">{review.hotel_name}</div>
                              <div className="review__date">{formatDate(review.created_at)}</div>
                            </div>
                            <div className="grow" />
                            <StarRating value={review.rating} showValue={false} size={13} />
                          </div>
                          {review.title ? <h4 className="review__title">{review.title}</h4> : null}
                          <p className="review__body">{review.comment}</p>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <div className="empty">
                      <Icon name="star" size={28} className="empty__icon" />
                      <p>You haven&apos;t written any reviews yet.</p>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
