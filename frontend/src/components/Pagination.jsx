import Icon from './Icon'

/** Compact pagination with ellipses for long result sets. */
export default function Pagination({ page = 1, pageCount = 1, onChange, disabled = false }) {
  if (pageCount <= 1) return null

  const pages = []
  const push = (value) => pages.push(value)

  push(1)
  for (let current = page - 1; current <= page + 1; current += 1) {
    if (current > 1 && current < pageCount) push(current)
  }
  if (pageCount > 1) push(pageCount)

  const unique = [...new Set(pages)].sort((a, b) => a - b)
  const items = []
  unique.forEach((value, index) => {
    if (index > 0 && value - unique[index - 1] > 1) items.push({ ellipsis: true, key: `gap-${value}` })
    items.push({ value, key: value })
  })

  return (
    <nav className="pagination" aria-label="Pagination">
      <button
        type="button"
        className="pagination__btn"
        onClick={() => onChange(page - 1)}
        disabled={disabled || page <= 1}
        aria-label="Previous page"
      >
        <Icon name="chevron-left" size={16} />
      </button>

      {items.map((item) =>
        item.ellipsis ? (
          <span key={item.key} className="pagination__ellipsis">
            …
          </span>
        ) : (
          <button
            key={item.key}
            type="button"
            className={`pagination__btn ${item.value === page ? 'is-active' : ''}`.trim()}
            onClick={() => onChange(item.value)}
            disabled={disabled}
            aria-current={item.value === page ? 'page' : undefined}
          >
            {item.value}
          </button>
        ),
      )}

      <button
        type="button"
        className="pagination__btn"
        onClick={() => onChange(page + 1)}
        disabled={disabled || page >= pageCount}
        aria-label="Next page"
      >
        <Icon name="chevron-right" size={16} />
      </button>
    </nav>
  )
}
