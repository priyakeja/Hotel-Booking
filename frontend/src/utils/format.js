/** Shared formatting helpers. */

export function formatMoney(value, symbol = '₹', { decimals = 0 } = {}) {
  const number = Number(value ?? 0)
  if (Number.isNaN(number)) return `${symbol}0`
  return `${symbol}${number.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}

export function formatDate(value, options = {}) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString('en-US', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
    ...options,
  })
}

/** Long form: "15 Jan, 2025" */
export function formatDateShort(value) {
  return formatDate(value, { day: '2-digit', month: 'short' })
}

export function toISODate(date) {
  if (!date) return ''
  const value = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(value.getTime())) return ''
  return value.toISOString().slice(0, 10)
}

export function todayISO() {
  return toISODate(new Date())
}

export function addDays(value, days) {
  const date = value instanceof Date ? new Date(value) : new Date(value || Date.now())
  date.setDate(date.getDate() + days)
  return date
}

export function nightsBetween(checkIn, checkOut) {
  if (!checkIn || !checkOut) return 0
  const start = new Date(`${checkIn}T00:00:00Z`)
  const end = new Date(`${checkOut}T00:00:00Z`)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0
  return Math.max(0, Math.round((end - start) / 86400000))
}

export function initials(name = '') {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

export function truncate(text = '', length = 120) {
  if (text.length <= length) return text
  return `${text.slice(0, length).trimEnd()}…`
}

export function pluralise(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`
}

/** Maps a booking status to a badge modifier. */
export function statusTone(status) {
  switch (status) {
    case 'confirmed':
      return 'success'
    case 'checked_in':
      return 'info'
    case 'completed':
      return 'navy'
    case 'cancelled':
      return 'danger'
    case 'pending':
    default:
      return 'warning'
  }
}
