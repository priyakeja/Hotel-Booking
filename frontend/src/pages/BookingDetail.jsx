import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import Icon from '../components/Icon'
import { Loader } from '../components/Loader'
import Reveal from '../components/Reveal'
import { useSite } from '../context/SiteContext'
import { useToast } from '../context/ToastContext'
import useFetch from '../hooks/useFetch'
import { formatDate, formatMoney, pluralise, statusTone } from '../utils/format'

/** Payment status badge modifier — deliberately independent of booking status. */
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

/**
 * Booking details for a single reservation.
 *
 * The reference is used as the lookup key, and the backend scopes the API to the
 * signed-in customer — requesting someone else's reference returns 404.
 */
export default function BookingDetail() {
  const { reference } = useParams()
  const { currency } = useSite()
  const toast = useToast()
  const [cancelling, setCancelling] = useState(false)
  const { data: booking, loading, error, reload } = useFetch(
    (signal) => api.bookings.detail(reference, { signal }),
    [reference],
  )

  const cancelBooking = async () => {
    setCancelling(true)
    try {
      await api.bookings.cancel(reference)
      toast.success(`Booking ${reference} cancelled.`)
      reload()
    } catch (cancelError) {
      toast.error(cancelError.message)
    } finally {
      setCancelling(false)
    }
  }

  return (
    <>
      <section className="page-hero" style={{ paddingBottom: 'var(--space-7)' }}>
        <div className="container">
          <div className="breadcrumb">
            <Link to="/">Home</Link>
            <span className="breadcrumb__sep">/</span>
            <Link to="/dashboard">Dashboard</Link>
            <span className="breadcrumb__sep">/</span>
            <Link to="/dashboard/bookings">My Bookings</Link>
            <span className="breadcrumb__sep">/</span>
            <span>{reference}</span>
          </div>
          <h1>Booking details</h1>
          <p>Everything about reservation {reference}, straight from your account.</p>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="container">
          {loading ? <Loader label="Loading booking…" /> : null}

          {!loading && (error || !booking) ? (
            <div className="panel">
              <div className="empty">
                <Icon name="info" size={30} className="empty__icon" />
                <h3>We couldn&apos;t load this booking</h3>
                <p className="tiny">{error?.message || 'This reservation could not be found on your account.'}</p>
                <div className="row-center" style={{ justifyContent: 'center', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
                  <button type="button" className="btn btn--gold btn--sm" onClick={reload}>
                    Try Again
                  </button>
                  <Link to="/dashboard/bookings" className="btn btn--outline btn--sm">
                    Back to My Bookings
                  </Link>
                </div>
              </div>
            </div>
          ) : null}

          {!loading && booking ? (
            <Reveal>
              <div className="booking-detail">
                <div className="stack" style={{ gap: 'var(--space-5)' }}>
                  <div className="panel">
                    <div className="booking-detail__head">
                      <div className="booking-detail__media">
                        {booking.room_detail?.hotel_image || booking.room_detail?.room_image ? (
                          <img
                            src={booking.room_detail?.hotel_image || booking.room_detail?.room_image}
                            alt={booking.room_detail?.name || 'Room'}
                          />
                        ) : (
                          <span className="stay-card__placeholder">
                            <Icon name="building" size={26} />
                          </span>
                        )}
                      </div>
                      <div className="grow">
                        <h2 className="booking-detail__hotel">{booking.room_detail?.hotel_name}</h2>
                        <span className="muted tiny">
                          {booking.room_detail?.name} · <strong>{booking.reference}</strong>
                        </span>
                        <div className="booking-detail__badges">
                          <span className={`badge badge--${statusTone(booking.status)}`}>
                            {booking.status_display}
                          </span>
                          <span className={`badge badge--${paymentTone(booking.payment_status)}`}>
                            Payment: {booking.payment_status_display || 'Unpaid'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="stay-detail-grid">
                      <div className="stay-detail">
                        <span className="stay-detail__label">
                          <Icon name="calendar" size={13} /> Check-in
                        </span>
                        <strong>{formatDate(booking.check_in)}</strong>
                      </div>
                      <div className="stay-detail">
                        <span className="stay-detail__label">
                          <Icon name="calendar" size={13} /> Check-out
                        </span>
                        <strong>{formatDate(booking.check_out)}</strong>
                      </div>
                      <div className="stay-detail">
                        <span className="stay-detail__label">
                          <Icon name="clock" size={13} /> Nights
                        </span>
                        <strong>{booking.nights}</strong>
                      </div>
                      <div className="stay-detail">
                        <span className="stay-detail__label">
                          <Icon name="users" size={13} /> Guests
                        </span>
                        <strong>{booking.guests}</strong>
                      </div>
                      <div className="stay-detail">
                        <span className="stay-detail__label">
                          <Icon name="bed" size={13} /> Rooms
                        </span>
                        <strong>{booking.rooms_count}</strong>
                      </div>
                    </div>
                  </div>

                  <div className="panel">
                    <h3 className="panel__title">Guest details</h3>
                    <div className="booking-summary__rows">
                      <span className="booking-summary__row">
                        <span>Name</span>
                        <strong>{booking.guest_name}</strong>
                      </span>
                      <span className="booking-summary__row">
                        <span>Email</span>
                        <strong>{booking.guest_email}</strong>
                      </span>
                      {booking.guest_phone ? (
                        <span className="booking-summary__row">
                          <span>Phone</span>
                          <strong>{booking.guest_phone}</strong>
                        </span>
                      ) : null}
                      {booking.special_requests ? (
                        <span className="booking-summary__row">
                          <span>Special requests</span>
                          <strong>{booking.special_requests}</strong>
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>

                <aside className="booking-detail__aside">
                  <div className="panel">
                    <h3 className="panel__title">Payment summary</h3>
                    <div className="booking-summary__rows">
                      <span className="booking-summary__row">
                        <span>Method</span>
                        <strong>{booking.payment_provider === 'cash' ? 'Cash (pay at hotel)' : 'Online (Razorpay)'}</strong>
                      </span>
                      <span className="booking-summary__row">
                        <span>Payment status</span>
                        <strong>{booking.payment_status_display || 'Unpaid'}</strong>
                      </span>
                      {booking.payment_provider === 'cash' ? (
                        <>
                          <span className="booking-summary__row">
                            <span>Cash received</span>
                            <strong>{formatMoney(booking.cash_received, currency)}</strong>
                          </span>
                          <span className="booking-summary__row">
                            <span>Remaining</span>
                            <strong>{formatMoney(booking.cash_remaining, currency)}</strong>
                          </span>
                        </>
                      ) : null}
                    </div>

                    <div className="booking-summary__rows" style={{ borderTop: 0, paddingTop: 0 }}>
                      <span className="booking-summary__row">
                        <span>
                          {formatMoney(booking.price_per_night, currency)} × {pluralise(booking.nights, 'night')}
                          {booking.rooms_count > 1 ? ` × ${booking.rooms_count} rooms` : ''}
                        </span>
                        <span>{formatMoney(booking.subtotal, currency)}</span>
                      </span>
                      {Number(booking.tax_amount) > 0 ? (
                        <span className="booking-summary__row">
                          <span>Taxes &amp; fees</span>
                          <span>{formatMoney(booking.tax_amount, currency)}</span>
                        </span>
                      ) : null}
                    </div>

                    <div className="booking-summary__total">
                      <span className="muted">Total</span>
                      <span className="price__amount">{formatMoney(booking.total_price, currency)}</span>
                    </div>

                    {booking.can_be_cancelled ? (
                      <button
                        type="button"
                        className="btn btn--outline btn--block"
                        onClick={cancelBooking}
                        disabled={cancelling}
                      >
                        {cancelling ? 'Cancelling…' : 'Cancel booking'}
                      </button>
                    ) : null}

                    <Link to="/dashboard/bookings" className="btn btn--ghost btn--block" style={{ marginTop: 'var(--space-3)' }}>
                      <Icon name="arrow-left" size={15} /> Back to My Bookings
                    </Link>
                  </div>
                </aside>
              </div>
            </Reveal>
          ) : null}
        </div>
      </section>
    </>
  )
}
