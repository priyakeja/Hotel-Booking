import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import Gallery from '../components/Gallery'
import Icon from '../components/Icon'
import { Loader } from '../components/Loader'
import Reveal from '../components/Reveal'
import { usePageMeta, useSite } from '../context/SiteContext'
import useFetch from '../hooks/useFetch'
import { formatMoney, nightsBetween, todayISO } from '../utils/format'
import { discountLabel, offerBookUrl, validityLabel } from '../utils/offers'

export default function OfferDetail() {
  const { slug } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { currency } = useSite()

  const bookIntent = searchParams.get('book') === '1'

  const params = useMemo(
    () => ({
      check_in: searchParams.get('check_in') || '',
      check_out: searchParams.get('check_out') || '',
    }),
    [searchParams],
  )

  const { data: offer, loading, error } = useFetch(
    (signal) => api.offers.detail(slug, params, { signal }),
    [slug, params],
  )

  // Default the date pickers to a sensible 2-night stay.
  const [stay, setStay] = useState({
    check_in: params.check_in || todayISO(),
    check_out: '',
    guests: Number(searchParams.get('guests')) || 2,
    roomId: '',
  })

  useEffect(() => {
    if (!stay.check_out) {
      const start = new Date(`${stay.check_in}T00:00:00Z`)
      const minNights = offer?.min_stay || 2
      const end = new Date(start.getTime() + minNights * 86400000)
      setStay((current) => ({ ...current, check_out: end.toISOString().slice(0, 10) }))
    }
  }, [stay.check_in, stay.check_out, offer])

  useEffect(() => {
    if (offer?.rooms?.length && !stay.roomId) {
      setStay((current) => ({ ...current, roomId: String(offer.rooms[0].id) }))
    }
  }, [offer, stay.roomId])

  // Fire-and-forget view counter (real analytics, not faked).
  useEffect(() => {
    if (offer?.slug) api.offers.track(offer.slug, 'view').catch(() => {})
  }, [offer?.slug])

  useEffect(() => {
    if (bookIntent && !loading) {
      const target = document.getElementById('offer-book')
      target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [bookIntent, loading])

  usePageMeta({
    title: offer ? `${discountLabel(offer, currency)} ${offer.hotel?.name} | ${offer.title}` : undefined,
    description: offer?.short_description,
  })

  if (loading && !offer) {
    return (
      <div className="container section">
        <Loader label="Loading this offer…" />
      </div>
    )
  }

  if (error || !offer) {
    return (
      <div className="container section">
        <div className="empty">
          <Icon name="tag" size={34} className="empty__icon" />
          <h3>We couldn&apos;t find that offer</h3>
          <p className="tiny">{error?.message || 'It may have expired or been unpublished.'}</p>
          <Link to="/offers" className="btn btn--gold">
            Back to all offers
          </Link>
        </div>
      </div>
    )
  }

  const hotel = offer.hotel || {}
  const expired = offer.status === 'expired'
  const nights = nightsBetween(stay.check_in, stay.check_out)
  const minStay = offer.min_stay || 1
  const maxStay = offer.max_stay || 0
  const nightsOk = nights >= minStay && (!maxStay || nights <= maxStay)

  // Category and offer type are separate admin choices that often share a label
  // ("Weekend", "Long Stay", "Luxury"). Show each label only once.
  const metaBadges = []
  if (offer.category?.name) {
    metaBadges.push({ key: 'category', text: offer.category.name, className: 'badge badge--navy' })
  }
  if (
    offer.offer_type_display &&
    !metaBadges.some((badge) => badge.text.trim().toLowerCase() === offer.offer_type_display.trim().toLowerCase())
  ) {
    metaBadges.push({ key: 'type', text: offer.offer_type_display, className: 'badge' })
  }

  const bookNow = () => {
    if (expired) return
    api.offers.track(offer.slug, 'click').catch(() => {})
    navigate(offerBookUrl(offer, stay.roomId, {
      checkIn: stay.check_in,
      checkOut: stay.check_out,
      guests: stay.guests,
    }))
  }

  return (
    <>
      <section className="section-tight" style={{ background: 'var(--surface)' }}>
        <div className="container">
          <div className="breadcrumb">
            <Link to="/">Home</Link>
            <span className="breadcrumb__sep">/</span>
            <Link to="/offers">Offers</Link>
            <span className="breadcrumb__sep">/</span>
            <span>{offer.title}</span>
          </div>

          <Reveal>
            <Gallery
              images={offer.images}
              cover={offer.image}
              title={offer.title}
              badge={
                <span className="badge badge--gold">
                  <Icon name="tag" size={12} /> {discountLabel(offer, currency)}
                </span>
              }
            />
          </Reveal>

          <div className="offer-detail__pricebar">
            <span className="offer-detail__badge">
              <Icon name="tag" size={14} /> {discountLabel(offer, currency)}
            </span>
            {expired ? <span className="badge badge--danger">Expired</span> : null}
            <span className="offer-detail__hotel">
              <Icon name="building" size={14} /> {hotel.name}
              {hotel.location ? <span className="muted"> · {hotel.location}</span> : null}
            </span>
          </div>

          <div className="detail-head">
            <div>
              <h1 className="detail-head__title">{offer.title}</h1>
              {offer.short_description ? <p className="muted">{offer.short_description}</p> : null}
              <div className="detail-head__meta">
                {metaBadges.map((badge) => (
                  <span key={badge.key} className={badge.className}>
                    {badge.text}
                  </span>
                ))}
                {offer.promo_code_enabled && offer.promo_code ? (
                  <span className="badge badge--gold-alert">
                    Use code: {offer.promo_code}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="detail-cta offer-detail__cta">
              <span className="tiny muted">Offer price</span>
              <span className="offer-detail__prices">
                <span className="offer-detail__was">{formatMoney(offer.original_price, currency)}</span>
                <span className="offer-detail__now">{formatMoney(offer.offer_price, currency)}</span>
                <span className="price__unit">/ night</span>
              </span>
              {Number(offer.saving) > 0 ? (
                <span className="offer-detail__save">Save {formatMoney(offer.saving, currency)}/night</span>
              ) : null}
              <span className="tiny muted">+ taxes & fees</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 'var(--space-6)' }}>
        <div className="container">
          <div className="detail-panels">
            <div>
              {offer.description ? (
                <div className="panel">
                  <h3 className="panel__title">Offer description</h3>
                  <p className="muted">{offer.description}</p>
                </div>
              ) : null}

              {offer.benefits?.length ? (
                <div className="panel">
                  <h3 className="panel__title">What&apos;s included</h3>
                  <ul className="highlight-list">
                    {offer.benefits.map((benefit) => (
                      <li key={benefit.id}>
                        <Icon name="check" size={15} />
                        <span>{benefit.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="panel">
                <h3 className="panel__title">Stay requirements</h3>
                <ul className="highlight-list">
                  <li>
                    <Icon name="clock" size={15} />
                    <span>
                      Valid for stays between {offer.valid_from} and {offer.valid_until}
                    </span>
                  </li>
                  {offer.min_stay ? (
                    <li>
                      <Icon name="users" size={15} />
                      <span>Minimum stay: {offer.min_stay} night(s)</span>
                    </li>
                  ) : null}
                  {offer.max_stay ? (
                    <li>
                      <Icon name="users" size={15} />
                      <span>Maximum stay: {offer.max_stay} night(s)</span>
                    </li>
                  ) : null}
                  {Number(offer.min_booking_amount) > 0 ? (
                    <li>
                      <Icon name="wallet" size={15} />
                      <span>Minimum booking amount: {formatMoney(offer.min_booking_amount, currency)}</span>
                    </li>
                  ) : null}
                  {offer.blackout_start && offer.blackout_end ? (
                    <li>
                      <Icon name="calendar" size={15} />
                      <span>
                        Blackout dates: {offer.blackout_start} – {offer.blackout_end}
                      </span>
                    </li>
                  ) : null}
                </ul>
              </div>

              {offer.rooms?.length ? (
                <div className="panel">
                  <h3 className="panel__title">Applicable rooms</h3>
                  <div className="stack" style={{ gap: 'var(--space-3)' }}>
                    {offer.rooms.map((room) => (
                      <div key={room.id} className="offer-room">
                        {room.image ? <img src={room.image} alt={room.name} loading="lazy" /> : null}
                        <div className="grow">
                          <strong>{room.name}</strong>
                          <span className="tiny muted" style={{ display: 'block' }}>
                            {room.room_type_display} · sleeps {room.max_guests}
                          </span>
                        </div>
                        <span className="offer-room__price">
                          {formatMoney(offer.offer_price, currency)}
                          <span className="price__unit">/night</span>
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {offer.terms?.length ? (
                <div className="panel">
                  <h3 className="panel__title">Terms &amp; Conditions</h3>
                  <ul className="terms-list">
                    {offer.terms.map((term) => (
                      <li key={term}>{term}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>

            {/* --- booking panel --------------------------------------- */}
            <aside>
              <div className="panel offer-book" id="offer-book">
                <h3 className="panel__title">Book this offer</h3>

                {expired ? (
                  <>
                    <div className="alert alert--warning">
                      <Icon name="info" size={16} />
                      <span>This offer has ended and can no longer be booked.</span>
                    </div>
                    <div className="stack" style={{ gap: 'var(--space-3)' }}>
                      <Link to={`/hotels/${hotel.slug}`} className="btn btn--gold btn--block">
                        View Hotel
                      </Link>
                      <Link to="/offers" className="btn btn--outline btn--block">
                        See Similar Offers
                      </Link>
                    </div>
                  </>
                ) : (
                  <>
                    <label className="field">
                      <span className="field__label">Room</span>
                      <select
                        className="select"
                        value={stay.roomId}
                        onChange={(event) => setStay((current) => ({ ...current, roomId: event.target.value }))}
                      >
                        {(offer.rooms || []).map((room) => (
                          <option key={room.id} value={room.id}>
                            {room.name}
                          </option>
                        ))}
                      </select>
                    </label>

                    <div className="guest-grid">
                      <label className="field">
                        <span className="field__label">Check-in</span>
                        <input
                          type="date"
                          className="input"
                          value={stay.check_in}
                          onChange={(event) => setStay((current) => ({ ...current, check_in: event.target.value }))}
                        />
                      </label>
                      <label className="field">
                        <span className="field__label">Check-out</span>
                        <input
                          type="date"
                          className="input"
                          min={stay.check_in}
                          value={stay.check_out}
                          onChange={(event) => setStay((current) => ({ ...current, check_out: event.target.value }))}
                        />
                      </label>
                    </div>

                    <label className="field">
                      <span className="field__label">Guests</span>
                      <input
                        type="number"
                        min="1"
                        max="12"
                        className="input"
                        value={stay.guests}
                        onChange={(event) => setStay((current) => ({ ...current, guests: event.target.value }))}
                      />
                    </label>

                    <div className="booking-summary__rows" style={{ borderTop: 0, paddingTop: 0 }}>
                      <span className="booking-summary__row">
                        <span>
                          {formatMoney(offer.offer_price, currency)} × {nights} night{nights === 1 ? '' : 's'}
                        </span>
                        <span>{formatMoney(Number(offer.offer_price) * nights, currency)}</span>
                      </span>
                      {Number(offer.saving) > 0 ? (
                        <span className="booking-summary__row">
                          <span>You save</span>
                          <strong className="gold-text">{formatMoney(Number(offer.saving) * nights, currency)}</strong>
                        </span>
                      ) : null}
                    </div>

                    {!nightsOk ? (
                      <div className="alert alert--warning">
                        <Icon name="info" size={16} />
                        <span>
                          This offer requires a minimum stay of {minStay} night(s)
                          {maxStay ? ` and a maximum of ${maxStay}` : ''}.
                        </span>
                      </div>
                    ) : null}

                    <button
                      type="button"
                      className="btn btn--gold btn--block btn--lg"
                      disabled={!offer.rooms?.length || !nightsOk}
                      onClick={bookNow}
                    >
                      Book This Offer
                      <Icon name="arrow-right" size={16} />
                    </button>
                    <p className="tiny muted center" style={{ marginTop: 'var(--space-3)' }}>
                      {validityLabel(offer)}
                    </p>
                  </>
                )}
              </div>

              <div className="panel" style={{ background: 'var(--gold-100)', borderColor: 'var(--gold-300)' }}>
                <h3 className="panel__title">Need help booking?</h3>
                <p className="tiny" style={{ marginBottom: 'var(--space-3)' }}>
                  Our team is available 24/7 to help with group bookings and offer eligibility.
                </p>
                <Link to="/contact" className="btn btn--outline btn--sm">
                  Contact support
                </Link>
              </div>
            </aside>
          </div>
        </div>
      </section>
    </>
  )
}
