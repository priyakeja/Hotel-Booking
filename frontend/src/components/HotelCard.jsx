import { useState } from 'react'
import { Link } from 'react-router-dom'

import { formatMoney, truncate } from '../utils/format'
import Icon from './Icon'
import StarRating from './StarRating'

/** Listing card used on the homepage and the hotels grid. */
export default function HotelCard({ hotel, currency = '₹', search = '', showFavorite = true }) {
  const [saved, setSaved] = useState(false)

  const query = search ? `?${search}` : ''
  const soldOut = hotel.is_available === false

  return (
    <article className="hotel-card">
      <div className="hotel-card__media">
        {hotel.image ? (
          <img src={hotel.image} alt={hotel.name} loading="lazy" />
        ) : (
          <div className="skeleton" style={{ width: '100%', height: '100%' }} />
        )}

        <div className="hotel-card__badges">
          <span className="badge badge--glass">
            <Icon name="star" size={12} />
            {hotel.star_rating ? Number(hotel.star_rating).toFixed(1) : 'New'}
          </span>
          {hotel.is_featured ? <span className="badge badge--gold">Featured</span> : <span />}
        </div>

        {showFavorite ? (
          <button
            type="button"
            className={`hotel-card__favorite ${saved ? 'is-on' : ''}`.trim()}
            style={{ position: 'absolute', right: 'var(--space-3)', bottom: 'var(--space-3)' }}
            onClick={() => setSaved((value) => !value)}
            aria-pressed={saved}
            aria-label={saved ? `Remove ${hotel.name} from favourites` : `Save ${hotel.name} to favourites`}
          >
            <Icon name="heart" size={16} />
          </button>
        ) : null}
      </div>

      <div className="hotel-card__body">
        <h3 className="hotel-card__title">
          <Link to={`/hotels/${hotel.slug}${query}`}>{hotel.name}</Link>
        </h3>

        <span className="hotel-card__location">
          <Icon name="map-pin" size={14} />
          {hotel.location || `${hotel.city}, ${hotel.country}`}
        </span>

        {hotel.short_description ? (
          <p className="hotel-card__desc">{truncate(hotel.short_description, 84)}</p>
        ) : null}

        {Number(hotel.rating) > 0 || Number(hotel.review_count) > 0 ? (
          <StarRating value={hotel.rating} count={hotel.review_count} />
        ) : (
          <span className="hotel-card__no-reviews tiny muted">No reviews yet</span>
        )}

        <div className="hotel-card__footer">
          <span className="price">
            <span className="price__amount">{formatMoney(hotel.starting_price ?? hotel.price_per_night, currency)}</span>
            <span className="price__unit">/ night</span>
          </span>
          <Link to={`/hotels/${hotel.slug}${query}`} className="btn btn--gold btn--sm">
            View Details
          </Link>
        </div>

        {soldOut ? (
          <span className="badge badge--danger" style={{ alignSelf: 'flex-start' }}>
            Sold out for your dates
          </span>
        ) : null}
      </div>
    </article>
  )
}
