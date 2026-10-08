import { useCallback, useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import { addDays, formatMoney, nightsBetween, toISODate, todayISO } from '../utils/format'
import Icon from './Icon'
import { Loader } from './Loader'

/**
 * Date-based availability checker for a single room.
 *
 * Calls `/api/rooms/<id>/availability/` which reports how many identical rooms
 * are still free for the range and quotes the total price.
 *
 * The guest count is an input from the search context; the *rooms* to book are
 * derived from it (how many guests fit in one room), so the customer picks the
 * suggested number of rooms instead of working out the party size here.
 */
export default function AvailabilityChecker({
  room,
  defaults = {},
  currency = '$',
  onProceed,
  proceedLabel = 'Proceed to Book',
  onQuote,
}) {
  // Default to a two-night stay when no dates were carried in from a search, so
  // the checker can quote immediately without the visitor filling both fields.
  const initialCheckIn = defaults.check_in || todayISO()

  // Guests come from the search (or the room's own capacity); the suggested
  // room count is the party size divided by how many guests one room sleeps.
  const party = useMemo(() => {
    const guests = Math.max(Number(defaults.guests) || Number(room?.capacity) || 2, 1)
    const perRoom = Math.max(Number(room?.max_guests) || guests || 1, 1)
    return { guests, perRoom, rooms: Math.max(1, Math.ceil(guests / perRoom)) }
  }, [defaults.guests, room?.capacity, room?.max_guests])

  // Offer at least the suggested number of rooms, plus the rest of the
  // inventory in case a larger group wants extra rooms.
  const roomOptions = Math.max(
    party.rooms,
    Math.min(Number(room?.total_rooms) || 5, 8),
    Number(defaults.rooms) || 0,
  )

  const [form, setForm] = useState({
    check_in: initialCheckIn,
    check_out: defaults.check_out || toISODate(addDays(initialCheckIn, 2)),
    rooms: Math.max(party.rooms, Number(defaults.rooms) || 0),
  })
  const [quote, setQuote] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const update = (key) => (event) => {
    const value = event.target.value
    setForm((current) => {
      const next = { ...current, [key]: value }
      if (key === 'check_in' && next.check_out && next.check_out <= value) next.check_out = ''
      return next
    })
  }

  const check = useCallback(async () => {
    if (!room?.id) return
    if (!form.check_in || !form.check_out) {
      setError('Pick both a check-in and a check-out date.')
      setQuote(null)
      onQuote?.(null, form)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await api.rooms.availability(room.id, {
        check_in: form.check_in,
        check_out: form.check_out,
        guests: party.guests,
        rooms: form.rooms,
      })
      setQuote(data)
      // Hand the parent the quote together with the dates/rooms it belongs to.
      onQuote?.(data, { ...form, guests: party.guests })
    } catch (requestError) {
      setError(requestError.message)
      setQuote(null)
      onQuote?.(null, form)
    } finally {
      setLoading(false)
    }
  }, [room?.id, form, onQuote])

  // Re-quote automatically when dates arrive pre-filled from a search.
  useEffect(() => {
    if (room?.id && form.check_in && form.check_out) check()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [room?.id])

  // Changing the room count re-prices the quote, so the total always matches
  // the party size the visitor just selected.
  useEffect(() => {
    if (quote && room?.id && form.check_in && form.check_out) check()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.rooms])

  const nights = nightsBetween(form.check_in, form.check_out)
  const available = quote?.is_available

  return (
    <div>
      <div className="guest-grid">
        <label className="field">
          <span className="field__label">Check In</span>
          <input
            type="date"
            className="input"
            min={todayISO()}
            value={form.check_in}
            onChange={update('check_in')}
          />
        </label>
        <label className="field">
          <span className="field__label">Check Out</span>
          <input
            type="date"
            className="input"
            min={form.check_in || todayISO()}
            value={form.check_out}
            onChange={update('check_out')}
          />
        </label>
      </div>

      <label className="field">
        <span className="field__label">Rooms</span>
        <select className="select" value={form.rooms} onChange={update('rooms')}>
          {Array.from({ length: roomOptions }, (_, index) => index + 1).map((count) => (
            <option key={count} value={count}>
              {count} Room{count > 1 ? 's' : ''}
            </option>
          ))}
        </select>
        <span className="field__hint">
          {party.guests} guest{party.guests === 1 ? '' : 's'} · {party.perRoom} guest
          {party.perRoom === 1 ? '' : 's'} per room
          {Number(form.rooms) === party.rooms
            ? ` — ${party.rooms} room${party.rooms === 1 ? '' : 's'} suggested for your party`
            : ` — ${party.rooms} room${party.rooms === 1 ? '' : 's'} suggested`}
        </span>
      </label>

      <div className="row-between" style={{ marginTop: 'var(--space-2)' }}>
        <span className="price">
          <span className="price__amount">{formatMoney(room?.price_per_night, currency)}</span>
          <span className="price__unit">/ night</span>
        </span>
        <button type="button" className="btn btn--outline" onClick={check} disabled={loading || nights <= 0}>
          {loading ? 'Checking…' : 'Check Availability'}
        </button>
      </div>

      {loading ? <Loader label="Checking live availability…" inline /> : null}

      {error ? (
        <div className="alert alert--error" style={{ marginTop: 'var(--space-4)' }}>
          <Icon name="info" size={16} />
          <span>{error}</span>
        </div>
      ) : null}

      {quote && !loading ? (
        <div className={`availability-box ${available ? 'availability-box--ok' : 'availability-box--fail'}`}>
          <div className="row-between">
            <span className="row-center" style={{ gap: 8 }}>
              <Icon name={available ? 'check-circle' : 'info'} size={17} />
              <strong style={{ fontSize: 'var(--text-base)' }}>
                {available
                  ? `🟢 ${quote.rooms_left} room${quote.rooms_left > 1 ? 's' : ''} available for your selected dates`
                  : '🔴 Sold out for selected dates'}
              </strong>
            </span>
          </div>

          <p className="tiny" style={{ margin: 'var(--space-2) 0 var(--space-3)' }}>
            {quote.message}
          </p>

          <div className="booking-summary__rows" style={{ margin: 0, paddingBottom: 0, borderBottom: 0 }}>
            <span className="booking-summary__row">
              <span>
                {currency}
                {Number(quote.price_per_night).toFixed(0)} × {quote.nights} night
                {quote.nights === 1 ? '' : 's'}
                {Number(quote.rooms) > 1 ? ` × ${quote.rooms} rooms` : ''}
              </span>
              <span>{formatMoney(quote.subtotal, currency)}</span>
            </span>
            {Number(quote.tax_amount) > 0 ? (
              <span className="booking-summary__row">
                <span>Taxes &amp; fees</span>
                <span>{formatMoney(quote.tax_amount, currency)}</span>
              </span>
            ) : null}
            <span className="booking-summary__row" style={{ fontWeight: 700, color: 'var(--ink-900)' }}>
              <span>Total</span>
              <span>{formatMoney(quote.total_price, currency)}</span>
            </span>
          </div>

          {!quote.fits_guests ? (
            <p className="field__error" style={{ marginTop: 'var(--space-2)' }}>
              {party.perRoom} guests per room — increase the room count to fit {party.guests} guests.
            </p>
          ) : null}

          {onProceed && available && quote.fits_guests ? (
            <button
              type="button"
              className="btn btn--gold btn--block"
              style={{ marginTop: 'var(--space-4)' }}
              onClick={() =>
                onProceed({
                  ...quote,
                  rooms: form.rooms,
                  guests: party.guests,
                  check_in: form.check_in,
                  check_out: form.check_out,
                })
              }
            >
              {proceedLabel}
              <Icon name="arrow-right" size={16} />
            </button>
          ) : null}

        </div>
      ) : null}
    </div>
  )
}
