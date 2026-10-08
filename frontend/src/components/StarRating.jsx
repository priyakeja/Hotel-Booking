import Icon from './Icon'

/** Read-only star rating, optionally with the numeric value and review count. */
export default function StarRating({ value = 0, size = 14, showValue = true, count, className = '' }) {
  const rating = Number(value) || 0

  return (
    <span className={`rating ${className}`.trim()} title={`${rating.toFixed(1)} out of 5`}>
      <span className="rating__stars">
        {[1, 2, 3, 4, 5].map((star) => (
          <Icon
            key={star}
            name="star"
            size={size}
            style={{ opacity: star <= Math.round(rating) ? 1 : 0.28 }}
          />
        ))}
      </span>
      {showValue && rating > 0 ? <span className="rating__value">{rating.toFixed(1)}</span> : null}
      {count !== undefined && count !== null && count > 0 ? (
        <span className="rating__meta">({count} reviews)</span>
      ) : null}
    </span>
  )
}
