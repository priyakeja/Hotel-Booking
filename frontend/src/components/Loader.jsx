export function Loader({ label = 'Loading…', inline = false }) {
  return (
    <div className={`loader ${inline ? 'loader--inline' : ''}`.trim()} role="status">
      <span className="loader__ring" />
      {label ? <span>{label}</span> : null}
    </div>
  )
}

export function SkeletonCard() {
  return (
    <div className="skeleton-card">
      <div className="skeleton skeleton-card__media" />
      <div className="skeleton skeleton-line skeleton-line--md" />
      <div className="skeleton skeleton-line skeleton-line--sm" />
      <div className="skeleton skeleton-line" />
    </div>
  )
}

export function SkeletonGrid({ count = 6, columns = 3 }) {
  return (
    <div className={`grid grid--${columns}`}>
      {Array.from({ length: count }, (_, index) => (
        <SkeletonCard key={index} />
      ))}
    </div>
  )
}

export default Loader
