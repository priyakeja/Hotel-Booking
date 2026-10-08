import { Link } from 'react-router-dom'

import { formatMoney } from '../utils/format'
import Icon from './Icon'

/** Room row on the hotel detail page: image, specs, price and book action. */
export default function RoomCard({ room, hotelSlug, currency = '₹', search = '', onCheckAvailability }) {
  const soldOut = room.is_available === false

  // Carry the searched dates/guests through to the booking page.
  const bookParams = new URLSearchParams(search)
  bookParams.set('room', room.id)

  return (
    <article className="room-card">
      <div className="room-card__media">
        {room.image ? (
          <img src={room.image} alt={room.name} loading="lazy" />
        ) : (
          <div className="skeleton" style={{ width: '100%', height: '100%' }} />
        )}
      </div>

      <div>
        <h4 className="room-card__title">{room.name}</h4>
        <div className="room-card__meta">
          <span>
            <Icon name="users" size={14} />
            {room.capacity} Guests
          </span>
          {room.bed_type ? (
            <span>
              <Icon name="bed" size={14} />
              {room.bed_type}
            </span>
          ) : null}
          {room.size_sqm ? (
            <span>
              <Icon name="ruler" size={14} />
              {room.size_sqm} m²
            </span>
          ) : null}
          {room.rooms_left !== undefined && room.rooms_left !== null ? (
            <span className={room.rooms_left <= 2 && room.rooms_left > 0 ? 'gold-text' : ''}>
              {room.rooms_left > 0
                ? `🟢 ${room.rooms_left} room${room.rooms_left > 1 ? 's' : ''} available`
                : '🔴 Sold out for selected dates'}
            </span>
          ) : room.total_rooms ? (
            <span>
              🟢 {room.total_rooms} room{room.total_rooms > 1 ? 's' : ''} in inventory
            </span>
          ) : null}
        </div>

        {room.amenities?.length ? (
          <div className="amenity-inline">
            {room.amenities.slice(0, 4).map((amenity) => (
              <span key={amenity.id} className="amenity-inline__item">
                <Icon name={amenity.icon} size={13} />
                {amenity.name}
              </span>
            ))}
          </div>
        ) : null}
      </div>

      <div className="room-card__action">
        <span className="price">
          <span className="price__amount">{formatMoney(room.price_per_night, currency)}</span>
          <span className="price__unit">/ night</span>
        </span>
        {onCheckAvailability ? (
          <button
            type="button"
            className="btn btn--gold btn--sm"
            onClick={() => onCheckAvailability(room)}
            disabled={soldOut}
          >
            {soldOut ? 'Sold out' : 'Check Availability'}
          </button>
        ) : (
          <Link to={`/hotels/${hotelSlug}/book?${bookParams.toString()}`} className="btn btn--gold btn--sm">
            Check Availability
          </Link>
        )}
      </div>
    </article>
  )
}
