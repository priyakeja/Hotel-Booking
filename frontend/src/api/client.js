/**
 * Thin fetch wrapper around the Django REST API.
 *
 * - Adds the DRF token when the visitor is signed in.
 * - Normalises DRF error payloads into a single `ApiError` with a readable
 *   message plus the original per-field errors.
 */

const BASE_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api').replace(/\/+$/, '')
const TOKEN_KEY = 'skystay.token'

export class ApiError extends Error {
  constructor(message, status, fieldErrors = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

function humanise(payload, status) {
  if (!payload) return `Request failed (${status}).`
  if (typeof payload === 'string') return payload
  if (payload.detail) return payload.detail
  if (Array.isArray(payload)) return payload.join(' ')

  const fieldErrors = {}
  const parts = []
  for (const [field, value] of Object.entries(payload)) {
    const text = Array.isArray(value) ? value.join(' ') : String(value)
    fieldErrors[field] = text
    parts.push(field === 'non_field_errors' ? text : `${field}: ${text}`)
  }
  return parts.length ? parts.join(' • ') : `Request failed (${status}).`
}

async function request(path, { method = 'GET', body, auth = true, signal } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const token = auth ? tokenStore.get() : null
  if (token) headers.Authorization = `Token ${token}`

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      signal,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      `Cannot reach the API at ${BASE_URL}. Is the Django server running?`,
      0,
    )
  }

  if (response.status === 204) return null

  const text = await response.text()
  let payload = null
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = text
    }
  }

  if (!response.ok) {
    const message = humanise(payload, response.status)
    const fieldErrors = typeof payload === 'object' && payload && !Array.isArray(payload) ? payload : {}
    throw new ApiError(message, response.status, fieldErrors)
  }
  return payload
}

/** Build a query string, dropping empty values and expanding arrays. */
export function qs(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    if (Array.isArray(value)) {
      value.filter((v) => v !== '' && v !== undefined && v !== null).forEach((v) => search.append(key, v))
    } else {
      search.append(key, value)
    }
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

export const api = {
  baseUrl: BASE_URL,

  get: (path, options) => request(path, options),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),

  /* --- dynamic CMS content -------------------------------------------- */
  site: {
    settings: (options) => request('/settings/', options),
    // One shared contact payload feeds the Contact page, the contact cards and
    // the footer, so they can never drift apart.
    contact: (options) => request('/contact/', options),
    sendContactMessage: (payload, options) =>
      request('/contact/messages/', { ...options, method: 'POST', body: payload, auth: false }),
    home: (options) => request('/home/', options),
    navLinks: (location, options) => request(`/nav-links/${qs({ location })}`, options),
    amenities: (params, options) => request(`/amenities/${qs(params)}`, options),
    testimonials: (options) => request('/testimonials/', options),
    features: (options) => request('/features/', options),
    heroes: (options) => request('/heroes/', options),
    sections: (options) => request('/sections/', options),
    section: (key, options) => request(`/sections/${key}/`, options),
  },

  /* --- catalogue ------------------------------------------------------- */
  hotels: {
    list: (params, options) => request(`/hotels/${qs(params)}`, options),
    // `params` carries check_in/check_out so the nested rooms report live availability.
    detail: (slug, params, options) => request(`/hotels/${slug}/${qs(params)}`, options),
    filters: (options) => request('/hotels/filters/', options),
    availability: (slug, params, options) => request(`/hotels/${slug}/availability/${qs(params)}`, options),
  },
  rooms: {
    list: (params, options) => request(`/rooms/${qs(params)}`, options),
    detail: (id, options) => request(`/rooms/${id}/`, options),
    availability: (id, params, options) => request(`/rooms/${id}/availability/${qs(params)}`, options),
  },
  availability: {
    search: (params, options) => request(`/availability/${qs(params)}`, options),
  },

  /* --- bookings -------------------------------------------------------- */
  bookings: {
    list: (params, options) => request(`/bookings/${qs(params)}`, options),
    summary: (options) => request('/bookings/summary/', options),
    detail: (reference, options) => request(`/bookings/${reference}/`, options),
    create: (payload, options) => request('/bookings/', { ...options, method: 'POST', body: payload }),
    update: (reference, payload, options) => request(`/bookings/${reference}/`, { ...options, method: 'PATCH', body: payload }),
    cancel: (reference, options) => request(`/bookings/${reference}/cancel/`, { ...options, method: 'POST' }),
  },

  /* --- payments -------------------------------------------------------- */
  payments: {
    createOrder: (payload, options) => request('/payments/create-order/', { ...options, method: 'POST', body: payload }),
    verify: (payload, options) => request('/payments/verify/', { ...options, method: 'POST', body: payload }),
  },

  /* --- admin ----------------------------------------------------------- */
  admin: {
    testEmail: (email, options) => request('/admin/test-email/', { ...options, method: 'POST', body: { email } }),
  },

  /* --- offers / promotions -------------------------------------------- */
  offers: {
    list: (params, options) => request(`/offers/${qs(params)}`, options),
    // One call hydrating the Offers page (settings + featured + limited).
    page: (options) => request('/offers/page/', options),
    detail: (slug, params, options) => request(`/offers/${slug}/${qs(params)}`, options),
    featured: (options) => request('/offers/featured/', options),
    limited: (options) => request('/offers/limited/', options),
    categories: (options) => request('/offers/categories/', options),
    filters: (options) => request('/offers/filters/', options),
    track: (slug, event = 'view') =>
      request(`/offers/${slug}/track/`, { method: 'POST', body: { event }, auth: false }),
  },

  /* --- reviews --------------------------------------------------------- */
  reviews: {
    list: (params, options) => request(`/reviews/${qs(params)}`, options),
    create: (payload, options) => request('/reviews/', { ...options, method: 'POST', body: payload }),
  },


  /* --- auth ------------------------------------------------------------ */
  auth: {
    register: (payload) => request('/auth/register/', { method: 'POST', body: payload, auth: false }),
    login: (payload) => request('/auth/login/', { method: 'POST', body: payload, auth: false }),
    logout: () => request('/auth/logout/', { method: 'POST' }),
    me: (options) => request('/auth/me/', options),
    updateMe: (payload) => request('/auth/me/', { method: 'PATCH', body: payload }),
    changePassword: (payload) => request('/auth/change-password/', { method: 'POST', body: payload }),
  },
}

export default api
