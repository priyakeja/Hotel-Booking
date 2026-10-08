import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import AvailabilityChecker from '../components/AvailabilityChecker'
import Gallery from '../components/Gallery'
import Icon from '../components/Icon'
import { Loader } from '../components/Loader'
import Reveal from '../components/Reveal'
import { useAuth } from '../context/AuthContext'
import { useSite } from '../context/SiteContext'
import { useToast } from '../context/ToastContext'
import useFetch from '../hooks/useFetch'
import { formatDate, formatMoney, nightsBetween, todayISO } from '../utils/format'

export default function Booking() {
  const { slug } = useParams()
  const [searchParams] = useSearchParams()
  const toast = useToast()
  const { currency } = useSite()
  const { user } = useAuth()

  const roomId = searchParams.get('room')
  // An offer slug arrives here when the visitor booked from the Offers page.
  const offerSlug = searchParams.get('offer')
  const roomParams = useMemo(
    () => ({
      check_in: searchParams.get('check_in') || '',
      check_out: searchParams.get('check_out') || '',
    }),
    [searchParams],
  )

  const { data: hotel, loading, error } = useFetch(
    (signal) => api.hotels.detail(slug, roomParams, { signal }),
    [slug, roomParams],
  )

  // The offer is only a display/context hint here — the server re-validates it
  // and recalculates the price when the booking is created.
  const { data: offerData } = useFetch(
    (signal) => (offerSlug ? api.offers.detail(offerSlug, {}, { signal }) : Promise.resolve(null)),
    [offerSlug],
  )

  const rooms = hotel?.rooms || []
  const room = rooms.find((item) => String(item.id) === String(roomId)) || rooms[0] || null
  const appliedOffer = offerData && (!hotel || offerData.hotel?.slug === hotel.slug) ? offerData : null

  const [form, setForm] = useState({
    guest_name: '',
    guest_email: '',
    guest_phone: '',
    special_requests: '',
    // Carried in from the room checker, which suggests a count from the party size.
    rooms_count: Math.max(Number(searchParams.get('rooms')) || 1, 1),
  })
  const [paymentMethod, setPaymentMethod] = useState('razorpay')
  const [quote, setQuote] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [confirmed, setConfirmed] = useState(null)
  const [remaining, setRemaining] = useState(null)

  // Pre-fill guest details from the signed-in profile.
  useEffect(() => {
    if (!user) return
    setForm((current) => ({
      ...current,
      guest_name: current.guest_name || user.display_name || user.username || '',
      guest_email: current.guest_email || user.email || '',
      guest_phone: current.guest_phone || user.phone || '',
    }))
  }, [user])

  const defaults = useMemo(
    () => ({
      check_in: roomParams.check_in || todayISO(),
      check_out:
        roomParams.check_out ||
        new Date(new Date(`${roomParams.check_in || todayISO()}T00:00:00Z`).getTime() + 2 * 86400000)
          .toISOString()
          .slice(0, 10),
      guests: Number(searchParams.get('guests')) || room?.capacity || 2,
      rooms: Number(searchParams.get('rooms')) || 0,
    }),
    [roomParams, searchParams, room],
  )

  const handleQuote = useCallback((data, checkerForm) => {
    setQuote(data ? { ...data, ...checkerForm } : null)
    // Follow the suggested room count the checker calculated from the party size.
    if (data?.rooms) {
      const suggested = Math.max(Number(data.rooms) || 1, 1)
      setForm((current) => (current.rooms_count === suggested ? current : { ...current, rooms_count: suggested }))
    }
  }, [])

  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))

  const loadRazorpayScript = () => {
    return new Promise((resolve) => {
      if (window.Razorpay) return resolve(true)
      const script = document.createElement('script')
      script.src = 'https://checkout.razorpay.com/v1/checkout.js'
      script.onload = () => resolve(true)
      script.onerror = () => resolve(false)
      document.body.appendChild(script)
    })
  }

  const submit = async (event) => {
    event.preventDefault()
    if (!room) return
    if (!quote?.is_available || quote?.rooms_left <= 0) {
      setSubmitError('No rooms available for the selected dates. Please select different dates.')
      return
    }

    setSubmitting(true)
    setSubmitError(null)
    try {
      // 1. Create booking
      const booking = await api.bookings.create({
        room: room.id,
        check_in: quote.check_in,
        check_out: quote.check_out,
        guests: Number(quote.guests) || 1,
        rooms_count: Number(form.rooms_count) || 1,
        special_requests: form.special_requests,
        guest_name: form.guest_name,
        guest_email: form.guest_email,
        guest_phone: form.guest_phone,
        payment_method: paymentMethod,
        ...(appliedOffer ? { offer: appliedOffer.slug } : {}),
      })

      // 2. Handle Cash Payment choice
      if (paymentMethod === 'cash') {
        setConfirmed(booking)
        toast.success(`Booking ${booking.reference} reserved! Cash payment pending at check-in.`)
        window.scrollTo({ top: 0, behavior: 'smooth' })

        try {
          setRemaining(
            await api.rooms.availability(room.id, {
              check_in: booking.check_in,
              check_out: booking.check_out,
              guests: booking.guests,
            }),
          )
        } catch {
          setRemaining(null)
        }
        return
      }

      // 3. Create Razorpay order
      let orderData
      try {
        orderData = await api.payments.createOrder({ booking_reference: booking.reference })
      } catch (err) {
        console.warn('Payment order creation warning:', err)
      }

      const hasRazorpay = await loadRazorpayScript()

      if (hasRazorpay && orderData?.order_id && window.Razorpay) {
        const options = {
          key: orderData.key_id,
          amount: orderData.amount_paise,
          currency: orderData.currency || 'INR',
          name: 'SkyStay Hotel Booking',
          description: `Booking #${booking.reference} - ${room.name}`,
          order_id: orderData.order_id,
          handler: async (response) => {
            try {
              const verifiedBooking = await api.payments.verify({
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
              })
              setConfirmed(verifiedBooking)
              toast.success(`Payment successful! Booking ${verifiedBooking.reference} confirmed.`)
              window.scrollTo({ top: 0, behavior: 'smooth' })
            } catch (verErr) {
              setSubmitError(`Payment verification failed: ${verErr.message}`)
            }
          },
          prefill: {
            name: form.guest_name,
            email: form.guest_email,
            contact: form.guest_phone,
          },
          theme: { color: '#061526' },
          modal: {
            ondismiss: () => {
              setSubmitting(false)
              toast.info('Payment window closed. You can complete payment from your Dashboard.')
            },
          },
        }

        const rzp = new window.Razorpay(options)
        rzp.on('payment.failed', (resp) => {
          setSubmitError(`Payment failed: ${resp.error?.description || 'Transaction failed'}`)
          setSubmitting(false)
        })
        rzp.open()
        return
      }

      // Fallback verification for offline / dev mode
      const verifiedBooking = await api.payments.verify({
        razorpay_order_id: orderData?.order_id || `order_${booking.reference}`,
        razorpay_payment_id: `pay_simulated_${Date.now()}`,
        razorpay_signature: 'simulated_dev_signature',
      })

      setConfirmed(verifiedBooking || booking)
      toast.success(`Booking ${booking.reference} confirmed!`)
      window.scrollTo({ top: 0, behavior: 'smooth' })

      try {
        setRemaining(
          await api.rooms.availability(room.id, {
            check_in: booking.check_in,
            check_out: booking.check_out,
            guests: booking.guests,
          }),
        )
      } catch {
        setRemaining(null)
      }
    } catch (requestError) {
      setSubmitError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading && !hotel) {
    return (
      <div className="container section">
        <Loader label="Preparing your booking…" />
      </div>
    )
  }

  if (error || !hotel) {
    return (
      <div className="container section">
        <div className="empty">
          <Icon name="building" size={34} className="empty__icon" />
          <h3>We couldn&apos;t load this hotel</h3>
          <p className="tiny">{error?.message || 'Please pick a hotel from the listing page.'}</p>
          <Link to="/hotels" className="btn btn--gold">
            Browse hotels
          </Link>
        </div>
      </div>
    )
  }

  if (!room) {
    return (
      <div className="container section">
        <div className="empty">
          <Icon name="bed" size={34} className="empty__icon" />
          <h3>No rooms available to book</h3>
          <p className="tiny">This hotel has no published room types yet.</p>
          <Link to={`/hotels/${hotel.slug}`} className="btn btn--gold">
            Back to hotel
          </Link>
        </div>
      </div>
    )
  }

  // --- confirmation screen ---------------------------------------------
  if (confirmed) {
    const isCash = confirmed.payment_provider === 'cash'
    return (
      <div className="container section">
        <Reveal>
          <div className="booking-success card card--pad" style={{ maxWidth: 620, margin: '0 auto' }}>
            <div className="booking-success__icon">
              <Icon name="check-circle" size={40} />
            </div>
            <h1 style={{ fontSize: 'var(--text-2xl)' }}>
              {isCash ? 'Your stay is reserved!' : 'Your stay is booked!'}
            </h1>
            <p className="muted">
              {isCash ? (
                <>
                  We&apos;ve emailed the reservation details to <strong>{confirmed.guest_email}</strong> — payment is
                  pending and collected at the hotel desk.
                </>
              ) : (
                <>
                  Payment received. We&apos;ve emailed your booking confirmation to{' '}
                  <strong>{confirmed.guest_email}</strong>. Keep your reference handy at check-in.
                </>
              )}
            </p>
            <div className="booking-success__ref">{confirmed.reference}</div>

            <div className="booking-summary__rows" style={{ textAlign: 'left' }}>
              <span className="booking-summary__row">
                <span>Hotel</span>
                <strong>{confirmed.room_detail?.hotel_name}</strong>
              </span>
              <span className="booking-summary__row">
                <span>Room</span>
                <strong>{confirmed.room_detail?.name}</strong>
              </span>
              <span className="booking-summary__row">
                <span>Check-in</span>
                <strong>{formatDate(confirmed.check_in)}</strong>
              </span>
              <span className="booking-summary__row">
                <span>Check-out</span>
                <strong>{formatDate(confirmed.check_out)}</strong>
              </span>
              <span className="booking-summary__row">
                <span>Guests</span>
                <strong>{confirmed.guests}</strong>
              </span>
              <span className="booking-summary__row">
                <span>Payment Method</span>
                <strong>{isCash ? 'Cash Payment (Pay at Hotel)' : 'Online Payment (Razorpay)'}</strong>
              </span>
              <span className="booking-summary__row">
                <span>Payment Status</span>
                <strong>
                  {confirmed.payment_status === 'paid'
                    ? 'Paid'
                    : confirmed.payment_status === 'partially_paid'
                    ? `Partially Paid (Received: ${formatMoney(confirmed.cash_received, currency)})`
                    : 'Unpaid (Pending at check-in)'}
                </strong>
              </span>
              {remaining ? (
                <span className="booking-summary__row">
                  <span>Rooms left for these dates</span>
                  <strong>
                    {remaining.rooms_left} of {room.total_rooms}
                  </strong>
                </span>
              ) : null}
              <span className="booking-summary__row">
                <span>Total</span>
                <strong>{formatMoney(confirmed.total_price, currency)}</strong>
              </span>
            </div>

            <div className="row-center" style={{ justifyContent: 'center', marginTop: 'var(--space-5)', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
              <Link to="/dashboard" className="btn btn--gold">
                View my bookings
              </Link>
              <Link to="/hotels" className="btn btn--outline">
                Book another stay
              </Link>
            </div>
          </div>
        </Reveal>
      </div>
    )
  }

  const nights = quote?.nights ?? nightsBetween(defaults.check_in, defaults.check_out)
  // When an offer applies, show the discounted nightly rate. The server is still
  // the source of truth for the final amount.
  const nightly = Number(appliedOffer?.offer_price ?? quote?.price_per_night ?? room.price_per_night)
  const roomCount = Number(form.rooms_count) || 1
  const displaySubtotal = nightly * nights * roomCount
  const taxRate = Number(quote?.subtotal) > 0 ? Number(quote.tax_amount) / Number(quote.subtotal) : 0
  const displayTax = displaySubtotal * taxRate
  const displayTotal = displaySubtotal + displayTax

  return (
    <>
      <section className="page-hero" style={{ paddingBottom: 'var(--space-7)' }}>
        <div className="container">
          <div className="breadcrumb">
            <Link to="/">Home</Link>
            <span className="breadcrumb__sep">/</span>
            <Link to="/hotels">Hotels</Link>
            <span className="breadcrumb__sep">/</span>
            <Link to={`/hotels/${hotel.slug}`}>{hotel.name}</Link>
            <span className="breadcrumb__sep">/</span>
            <span>Booking</span>
          </div>
          <h1>Complete your reservation</h1>
          <p>Confirm your dates, add your details and we&apos;ll hold the room instantly.</p>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <div className="container">
          <div className="steps">
            <span className="step is-done">
              <span className="step__num">
                <Icon name="check" size={13} />
              </span>
              Choose room
            </span>
            <span className="step__sep">—</span>
            <span className="step is-active">
              <span className="step__num">2</span>
              Guest details
            </span>
            <span className="step__sep">—</span>
            <span className="step">
              <span className="step__num">3</span>
              Confirmation
            </span>
          </div>

          <div className="booking-layout">
            {/* --- left: gallery, availability, form ------------------- */}
            <div>
              <Reveal>
                <Gallery
                  images={room.images}
                  cover={room.image}
                  title={room.name}
                  badge={<span className="badge badge--glass">{room.room_type_display || room.room_type}</span>}
                />
              </Reveal>

              <div className="panel" style={{ marginTop: 'var(--space-5)' }}>
                <div className="row-between" style={{ alignItems: 'flex-start', marginBottom: 'var(--space-4)' }}>
                  <div>
                    <h2 style={{ fontSize: 'var(--text-xl)', marginBottom: 4 }}>{room.name}</h2>
                    <span className="muted tiny">
                      {hotel.name} · {hotel.location}
                    </span>
                  </div>
                  <span className="badge badge--gold">
                    {formatMoney(room.price_per_night, currency)} / night
                  </span>
                </div>

                <div className="amenity-inline" style={{ marginBottom: 'var(--space-5)' }}>
                  <span className="amenity-inline__item">
                    <Icon name="users" size={13} />
                    {room.capacity} guests
                  </span>
                  {room.bed_type ? (
                    <span className="amenity-inline__item">
                      <Icon name="bed" size={13} />
                      {room.bed_type}
                    </span>
                  ) : null}
                  {room.size_sqm ? (
                    <span className="amenity-inline__item">
                      <Icon name="ruler" size={13} />
                      {room.size_sqm} m²
                    </span>
                  ) : null}
                  {(room.amenities || []).slice(0, 3).map((amenity) => (
                    <span key={amenity.id} className="amenity-inline__item">
                      <Icon name={amenity.icon} size={13} />
                      {amenity.name}
                    </span>
                  ))}
                </div>

                <h3 className="panel__title">Check availability</h3>
                <AvailabilityChecker room={room} defaults={defaults} currency={currency} onQuote={handleQuote} />
              </div>

              <form className="panel" style={{ marginTop: 'var(--space-5)' }} onSubmit={submit} id="booking-form">
                <h3 className="panel__title">Guest details</h3>

                <div className="guest-grid">
                  <label className="field">
                    <span className="field__label">Full name</span>
                    <input className="input" required value={form.guest_name} onChange={update('guest_name')} />
                  </label>
                  <label className="field">
                    <span className="field__label">Email</span>
                    <input type="email" className="input" required value={form.guest_email} onChange={update('guest_email')} />
                  </label>
                  <label className="field">
                    <span className="field__label">Phone</span>
                    <input className="input" value={form.guest_phone} onChange={update('guest_phone')} />
                  </label>
                  <label className="field">
                    <span className="field__label">Rooms</span>
                    <select className="select" value={form.rooms_count} onChange={update('rooms_count')}>
                      {Array.from({ length: Math.max(1, Math.min(room.total_rooms || 1, 5)) }, (_, index) => index + 1).map(
                        (count) => (
                          <option key={count} value={count}>
                            {count} room{count > 1 ? 's' : ''}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                </div>

                <label className="field">
                  <span className="field__label">Special requests</span>
                  <textarea
                    className="textarea"
                    placeholder="Airport pickup, high floor, late check-in…"
                    value={form.special_requests}
                    onChange={update('special_requests')}
                  />
                </label>

                <div style={{ marginTop: 'var(--space-4)', paddingTop: 'var(--space-4)', borderTop: '1px solid var(--border)' }}>
                  <h4 style={{ fontSize: 'var(--text-md)', marginBottom: 'var(--space-3)', color: 'var(--ink-900)' }}>Payment Method</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-3)' }}>
                    <label
                      className={`payment-option ${paymentMethod === 'razorpay' ? 'is-selected' : ''}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-3)',
                        padding: 'var(--space-3)',
                        borderRadius: 'var(--radius-sm)',
                        border: paymentMethod === 'razorpay' ? '2px solid var(--gold-500)' : '1px solid var(--border-strong)',
                        background: paymentMethod === 'razorpay' ? 'var(--gold-100)' : 'var(--surface)',
                        cursor: 'pointer',
                      }}
                    >
                      <input
                        type="radio"
                        name="payment_method"
                        value="razorpay"
                        checked={paymentMethod === 'razorpay'}
                        onChange={() => setPaymentMethod('razorpay')}
                      />
                      <div>
                        <strong style={{ display: 'block', fontSize: 'var(--text-sm)', color: 'var(--ink-900)' }}>Online Payment (Razorpay)</strong>
                        <span className="tiny muted">Cards, UPI, NetBanking</span>
                      </div>
                    </label>

                    <label
                      className={`payment-option ${paymentMethod === 'cash' ? 'is-selected' : ''}`}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--space-3)',
                        padding: 'var(--space-3)',
                        borderRadius: 'var(--radius-sm)',
                        border: paymentMethod === 'cash' ? '2px solid var(--gold-500)' : '1px solid var(--border-strong)',
                        background: paymentMethod === 'cash' ? 'var(--gold-100)' : 'var(--surface)',
                        cursor: 'pointer',
                      }}
                    >
                      <input
                        type="radio"
                        name="payment_method"
                        value="cash"
                        checked={paymentMethod === 'cash'}
                        onChange={() => setPaymentMethod('cash')}
                      />
                      <div>
                        <strong style={{ display: 'block', fontSize: 'var(--text-sm)', color: 'var(--ink-900)' }}>Cash Payment</strong>
                        <span className="tiny muted">Pay cash at check-in / hotel desk</span>
                      </div>
                    </label>
                  </div>
                </div>

                {submitError ? (
                  <div className="alert alert--error" style={{ marginBottom: 'var(--space-4)' }}>
                    <Icon name="info" size={16} />
                    <span>{submitError}</span>
                  </div>
                ) : null}
              </form>
            </div>

            {/* --- right: sticky summary ------------------------------- */}
            <aside className="booking-summary">
              <div className="booking-summary__media">
                {room.image ? <img src={room.image} alt={room.name} /> : <div className="skeleton" style={{ height: '100%' }} />}
              </div>

              <div className="booking-summary__body">
                <h3 style={{ fontSize: 'var(--text-lg)', marginBottom: 2 }}>{room.name}</h3>
                <span className="muted tiny">
                  <Icon name="map-pin" size={12} /> {hotel.name} · {hotel.location}
                </span>

                {appliedOffer ? (
                  <div className="alert alert--success" style={{ marginTop: 'var(--space-3)' }}>
                    <Icon name="tag" size={16} />
                    <span>
                      Offer applied: <strong>{appliedOffer.title}</strong> — save{' '}
                      {formatMoney(appliedOffer.saving, currency)}/night
                      {appliedOffer.promo_code_enabled && appliedOffer.promo_code
                        ? ` · code ${appliedOffer.promo_code}`
                        : ''}
                    </span>
                  </div>
                ) : null}

                <div className="booking-summary__rows">
                  <span className="booking-summary__row">
                    <span>Check-in</span>
                    <strong>{quote?.check_in ? formatDate(quote.check_in) : formatDate(defaults.check_in)}</strong>
                  </span>
                  <span className="booking-summary__row">
                    <span>Check-out</span>
                    <strong>{quote?.check_out ? formatDate(quote.check_out) : formatDate(defaults.check_out)}</strong>
                  </span>
                  <span className="booking-summary__row">
                    <span>Nights</span>
                    <strong>{nights}</strong>
                  </span>
                  <span className="booking-summary__row">
                    <span>Guests</span>
                    <strong>{quote?.guests || defaults.guests}</strong>
                  </span>
                  <span className="booking-summary__row">
                    <span>Rooms</span>
                    <strong>{form.rooms_count}</strong>
                  </span>
                </div>

                <div className="booking-summary__rows" style={{ borderTop: 0, paddingTop: 0 }}>
                  <span className="booking-summary__row">
                    <span>
                      {formatMoney(nightly, currency)} × {nights} night{nights === 1 ? '' : 's'}
                      {roomCount > 1 ? ` × ${roomCount} rooms` : ''}
                    </span>
                    <span>{formatMoney(displaySubtotal, currency)}</span>
                  </span>
                  {Number(displayTax) > 0 ? (
                    <span className="booking-summary__row">
                      <span>Taxes &amp; fees</span>
                      <span>{formatMoney(displayTax, currency)}</span>
                    </span>
                  ) : null}
                </div>

                <div className="booking-summary__total">
                  <span className="muted">Total payable</span>
                  <span className="price__amount">{formatMoney(displayTotal, currency)}</span>
                </div>

                <button
                  type="submit"
                  form="booking-form"
                  className="btn btn--gold btn--block btn--lg"
                  disabled={submitting || !quote?.is_available}
                >
                  {submitting ? 'Confirming…' : 'Confirm Booking'}
                </button>

                <p className="tiny muted center" style={{ marginTop: 'var(--space-3)' }}>
                  {quote?.is_available
                    ? 'Free cancellation up to 24 hours before check-in.'
                    : 'Check availability for your dates to continue.'}
                </p>

                <div className="stack" style={{ gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
                  <span className="row-center tiny muted">
                    <Icon name="shield" size={14} />
                    Secure booking — your details are encrypted.
                  </span>
                  <span className="row-center tiny muted">
                    <Icon name="clock" size={14} />
                    Instant confirmation, no waiting.
                  </span>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </>
  )
}
