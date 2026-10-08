/** Helpers shared by the offers page, offer detail and homepage deals section. */

import { formatMoney } from './format'

/**
 * Human label for an offer's discount, driven entirely by the backend's typed
 * fields — the correct format is never hard-coded per offer.
 */
export function discountLabel(offer, currency = '₹') {
  if (!offer) return ''
  const {
    discount_type: type,
    discount_value: value,
    free_nights: freeNights,
    discount_percent: percent,
  } = offer

  switch (type) {
    case 'percentage':
      return `${Number(percent) || Number(value) || 0}% OFF`
    case 'fixed':
      return `${formatMoney(value, currency)} OFF`
    case 'special_price':
      return `From ${formatMoney(value, currency)}`
    case 'free_night': {
      const nights = Number(freeNights) || 1
      return `${nights} Night${nights > 1 ? 's' : ''} Free`
    }
    case 'package':
      return 'Package Deal'
    default:
      return 'Special Deal'
  }
}

/** “Valid until Oct 31” or “Ends in 3 days” when the offer is closing soon. */
export function validityLabel(offer) {
  if (!offer) return ''
  const days = offer.days_until_end
  if (offer.ends_soon && days !== null && days >= 0) {
    if (days === 0) return 'Ends today'
    return `Ends in ${days} day${days === 1 ? '' : 's'}`
  }
  if (!offer.valid_until) return ''
  const date = new Date(`${offer.valid_until}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return ''
  const label = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
  return `Valid until ${label}`
}

/** Booking flow URL for an offer + room, carrying the offer context through. */
export function offerBookUrl(offer, roomId, { checkIn = '', checkOut = '', guests = 2 } = {}) {
  if (!offer?.hotel) return '/hotels'
  const params = new URLSearchParams()
  if (roomId) params.set('room', roomId)
  if (checkIn) params.set('check_in', checkIn)
  if (checkOut) params.set('check_out', checkOut)
  if (guests) params.set('guests', String(guests))
  params.set('offer', offer.slug)
  return `/hotels/${offer.hotel.slug}/book?${params.toString()}`
}

export default { discountLabel, validityLabel, offerBookUrl }
