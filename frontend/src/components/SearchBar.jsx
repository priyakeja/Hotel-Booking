import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { addDays, nightsBetween, toISODate, todayISO } from '../utils/format'
import Icon from './Icon'

//: Typical occupancy used to turn a party size into a room suggestion.
const GUESTS_PER_ROOM = 2

/** Rooms a party of this size needs, matching the room checker's suggestion. */
function suggestedRooms(guests) {
  return Math.max(1, Math.ceil(Math.max(Number(guests) || 1, 1) / GUESTS_PER_ROOM))
}

/**
 * Hero search form. Location is free text (matched against city/country/name by the
 * existing hotel API), dates drive real availability checks and guests the capacity
 * filter. Destination suggestions come from the same `/hotels/filters/` payload the
 * listing page uses, so there is no second search system.
 *
 * The party size is typed rather than picked from a dropdown, and the matching
 * room count is suggested next to it.
 */
export default function SearchBar({ locations = [], initial = {}, variant = 'hero' }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    location: initial.location || '',
    check_in: initial.check_in || todayISO(),
    check_out: initial.check_out || '',
    guests: initial.guests || 2,
  })
  const [error, setError] = useState(null)

  // Checkout must be at least one night after check-in.
  const minCheckout = useMemo(() => {
    const base = form.check_in ? new Date(`${form.check_in}T00:00:00Z`) : new Date()
    return toISODate(addDays(base, 1))
  }, [form.check_in])

  const update = (key) => (event) => {
    const value = event.target.value
    setError(null)
    setForm((current) => {
      const next = { ...current, [key]: value }
      // Keep the range valid: a checkout on/before check-in is cleared, not kept.
      if (key === 'check_in' && next.check_out && next.check_out <= value) {
        next.check_out = ''
      }
      return next
    })
  }

  const submit = (event) => {
    event.preventDefault()

    const today = todayISO()
    const location = form.location.trim()

    if (form.check_in && form.check_in < today) {
      setError('Check-in cannot be in the past.')
      return
    }
    if (form.check_out && form.check_out <= form.check_in) {
      setError('Check-out must be at least one night after check-in.')
      return
    }
    const guests = Number(form.guests)
    if (!Number.isInteger(guests) || guests < 1) {
      setError('Please enter at least one guest.')
      return
    }
    if (guests > 12) {
      setError('For more than 12 guests, please contact our team for a group booking.')
      return
    }

    const params = new URLSearchParams()
    if (location) params.set('search', location)
    if (form.check_in) params.set('check_in', form.check_in)
    if (form.check_out) params.set('check_out', form.check_out)
    params.set('guests', String(guests))
    navigate(`/hotels?${params.toString()}`)
  }

  const nights = nightsBetween(form.check_in, form.check_out)

  return (
    <form className={`searchbar searchbar--${variant}`} onSubmit={submit} noValidate>
      <div className="searchbar__card">
        <label className="searchbar__field">
          <span className="searchbar__label">
            <Icon name="map-pin" size={14} />
            Location
          </span>
          <input
            className="searchbar__input"
            list="skystay-locations"
            placeholder="Where are you going?"
            autoComplete="off"
            value={form.location}
            onChange={update('location')}
          />
          <datalist id="skystay-locations">
            {locations.map((location) => (
              <option key={location.label} value={location.city}>
                {location.label}
              </option>
            ))}
          </datalist>
        </label>

        <label className="searchbar__field">
          <span className="searchbar__label">
            <Icon name="calendar" size={14} />
            Check In
          </span>
          <input
            type="date"
            className="searchbar__input"
            min={todayISO()}
            value={form.check_in}
            onChange={update('check_in')}
          />
        </label>

        <label className="searchbar__field">
          <span className="searchbar__label">
            <Icon name="calendar" size={14} />
            Check Out
          </span>
          <input
            type="date"
            className="searchbar__input"
            min={minCheckout}
            value={form.check_out}
            onChange={update('check_out')}
          />
        </label>

        <label className="searchbar__field">
          <span className="searchbar__label">
            <Icon name="users" size={14} />
            Guests
          </span>
          <input
            type="number"
            className="searchbar__input"
            min="1"
            max="12"
            step="1"
            inputMode="numeric"
            value={form.guests}
            onChange={update('guests')}
          />
        </label>

        <button type="submit" className="btn btn--gold searchbar__submit">
          <Icon name="search" size={17} />
          Search
        </button>
      </div>

      {error ? (
        <p className="tiny searchbar__error" role="alert">
          <Icon name="info" size={13} /> {error}
        </p>
      ) : nights > 0 ? (
        <p className="tiny muted" style={{ marginTop: 8, marginLeft: 6 }}>
          {nights} {nights === 1 ? 'night' : 'nights'} · {Number(form.guests)} guest
          {Number(form.guests) > 1 ? 's' : ''} · {suggestedRooms(form.guests)} room
          {suggestedRooms(form.guests) > 1 ? 's' : ''} suggested
        </p>
      ) : null}
    </form>
  )
}
