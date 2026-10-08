import { Link } from 'react-router-dom'

import { formatMoney, truncate } from '../utils/format'
import { discountLabel, validityLabel } from '../utils/offers'
import Icon from './Icon'

/**
 * The Offers page uses its own card — deliberately *not* the hotel card — so a
 * visitor immediately reads “deal, savings and validity” rather than “hotel”.
 */
export default function OfferCard({ offer, currency = '₹', compact = false }) {
  if (!offer) return null

  const hotel = offer.hotel || {}
  const expired = offer.status === 'expired'
  const soldOut = offer.is_available === false

  return (
    <article className={`offer-card ${compact ? 'offer-card--compact' : ''}`.trim()}>
      <div className="offer-card__media">
        {offer.image ? (
          <img src={offer.image} alt={offer.title} loading="lazy" />
        ) : (
          <div className="skeleton" style={{ width: '100%', height: '100%' }} />
        )}

        <div className="offer-card__badges">
          <span className="offer-card__discount">
            <Icon name="tag" size={13} />
            {discountLabel(offer, currency)}
          </span>
          {offer.is_featured ? <span className="badge badge--gold">Featured</span> : null}
        </div>

        {expired ? <span className="offer-card__ribbon offer-card__ribbon--expired">Expired</span> : null}
        {!expired && offer.ends_soon ? (
          <span className="offer-card__ribbon offer-card__ribbon--soon">
            <Icon name="clock" size={12} />
            {validityLabel(offer)}
          </span>
        ) : null}
      </div>

      <div className="offer-card__body">
        <h3 className="offer-card__title">
          <Link to={`/offers/${offer.slug}`}>{offer.title}</Link>
        </h3>

        <span className="offer-card__hotel">
          <Icon name="building" size={13} />
          {hotel.name}
          {hotel.location ? <span className="muted"> · {hotel.location}</span> : null}
        </span>

        {offer.short_description ? (
          <p className="offer-card__desc">{truncate(offer.short_description, compact ? 70 : 110)}</p>
        ) : null}

        <div className="offer-card__price">
          <span className="offer-card__was">{formatMoney(offer.original_price, currency)}</span>
          <span className="offer-card__arrow">
            <Icon name="arrow-right" size={14} />
          </span>
          <span className="offer-card__now">{formatMoney(offer.offer_price, currency)}</span>
          <span className="offer-card__unit">/night</span>
        </div>
        {Number(offer.saving) > 0 ? (
          <span className="offer-card__save">
            <Icon name="trending-up" size={13} />
            Save {formatMoney(offer.saving, currency)}/night
          </span>
        ) : null}

        {!compact && offer.benefits?.length ? (
          <ul className="offer-card__benefits">
            {offer.benefits.slice(0, 3).map((benefit) => (
              <li key={benefit.id}>
                <Icon name="check" size={13} />
                {benefit.text}
              </li>
            ))}
          </ul>
        ) : null}

        <div className="offer-card__meta">
          {!compact ? <span className="offer-card__valid">{validityLabel(offer)}</span> : null}
          {offer.room_type_labels?.length ? (
            <span className="offer-card__rooms muted">
              <Icon name="bed" size={12} /> {offer.room_type_labels.slice(0, 2).join(', ')}
            </span>
          ) : null}
        </div>

        {soldOut && !expired ? (
          <span className="badge badge--danger" style={{ alignSelf: 'flex-start' }}>
            Sold out for your dates
          </span>
        ) : null}

        <div className="offer-card__actions">
          <Link to={`/offers/${offer.slug}`} className="btn btn--outline btn--sm">
            View Offer
          </Link>
          {expired ? (
            <Link to={`/hotels/${hotel.slug}`} className="btn btn--ghost btn--sm">
              View Hotel
            </Link>
          ) : (
            <Link to={`/offers/${offer.slug}?book=1`} className="btn btn--gold btn--sm">
              Book Now
            </Link>
          )}
        </div>
      </div>
    </article>
  )
}
