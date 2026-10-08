/**
 * Map helpers.
 *
 * The Contact page, its contact cards and the footer all point at the same
 * location, so every map URL is built here instead of in each component.
 * Coordinates always come from the CMS — nothing is hard-coded.
 */

/** Parse a `location` payload from the API into usable numbers. */
function coordinates(location) {
  const latitude = Number(location?.latitude)
  const longitude = Number(location?.longitude)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null
  return { latitude, longitude }
}

/** True when the location can be placed on a map. */
export function hasCoordinates(location) {
  return coordinates(location) !== null
}

/** "View on map" — Google Maps search, falling back to the written address. */
export function getMapUrl(location) {
  const point = coordinates(location)
  if (point) {
    return `https://www.google.com/maps/search/?api=1&query=${point.latitude},${point.longitude}`
  }
  const address = (location?.full_address || '').trim()
  return address ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}` : ''
}

/** "Get directions" — Google Maps directions to the coordinates. */
export function getDirectionsUrl(location) {
  const point = coordinates(location)
  if (point) {
    return `https://www.google.com/maps/dir/?api=1&destination=${point.latitude},${point.longitude}`
  }
  const address = (location?.full_address || '').trim()
  return address ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}` : ''
}

/**
 * Interactive OpenStreetMap embed centred on the coordinates with a marker.
 * Pan/zoom works inside the iframe and needs no API key or extra dependency.
 */
export function getEmbedMapUrl(location) {
  const point = coordinates(location)
  if (!point) return ''

  const span = 0.02
  const bbox = [
    point.longitude - span,
    point.latitude - span,
    point.longitude + span,
    point.latitude + span,
  ].join(',')

  return (
    'https://www.openstreetmap.org/export/embed.html' +
    `?bbox=${encodeURIComponent(bbox)}&layer=mapnik&marker=${point.latitude},${point.longitude}`
  )
}
