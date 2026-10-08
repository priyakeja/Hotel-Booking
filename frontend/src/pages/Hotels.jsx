import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import HotelCard from '../components/HotelCard'
import Icon from '../components/Icon'
import { SkeletonGrid } from '../components/Loader'
import Pagination from '../components/Pagination'
import Reveal from '../components/Reveal'
import { useSite } from '../context/SiteContext'
import useFetch from '../hooks/useFetch'
import { nightsBetween } from '../utils/format'

const SORTS = [
  ['popular', 'Popularity'],
  ['price_low', 'Price (low → high)'],
  ['price_high', 'Price (high → low)'],
  ['rating', 'Guest rating'],
  ['newest', 'Newest'],
]

const PAGE_SIZE = 9

//: Typical occupancy used to turn a party size into a room suggestion.
const GUESTS_PER_ROOM = 2

/** Rooms a party of this size needs, matching the room checker's suggestion. */
function suggestedRooms(guests) {
  return Math.max(1, Math.ceil(Math.max(Number(guests) || 1, 1) / GUESTS_PER_ROOM))
}

/** Reads repeated query params (`amenity=a&amenity=b`) into an array. */
function readList(params, key) {
  return params.getAll(key).filter(Boolean)
}

/** Human copy for the empty state, driven by the API's diagnostic reason. */
function emptyState(reason, destination) {
  switch (reason) {
    case 'location':
      return {
        title: destination ? `No hotels found in ${destination}.` : 'No hotels found for that destination.',
        hint: 'Check the spelling or try a different city.',
      }
    case 'availability':
      return {
        title: destination
          ? `Hotels were found in ${destination}, but none are available for your selected dates.`
          : 'No hotels are available for your selected dates.',
        hint: 'Try different dates or clear your filters.',
      }
    case 'capacity':
      return {
        title: 'No available rooms can accommodate your selected guests.',
        hint: 'Try fewer guests, more rooms, or different dates.',
      }
    case 'filters':
      return {
        title: 'No hotels match your selected filters.',
        hint: 'Try widening the price range or clearing a few filters.',
      }
    default:
      return {
        title: 'No hotels match your search.',
        hint: 'Try widening the price range or clearing a few filters.',
      }
  }
}

export default function Hotels() {
  const { currency, title } = useSite()
  const [searchParams, setSearchParams] = useSearchParams()
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [searchError, setSearchError] = useState('')

  // Paging lives in the querystring alongside the filters, so a shared link or a
  // refresh restores the exact page the visitor was looking at.
  const page = Math.max(1, Number(searchParams.get('page')) || 1)

  // --- filter state derived from the URL -------------------------------
  const query = useMemo(
    () => ({
      search: searchParams.get('search') || '',
      check_in: searchParams.get('check_in') || '',
      check_out: searchParams.get('check_out') || '',
      guests: searchParams.get('guests') || '',
      // Featured is opt-in only: it is applied solely when the URL says so (the
      // Featured Hotels experience or the explicit toggle below).
      featured: searchParams.get('featured') === 'true',
      sort: searchParams.get('sort') || 'popular',
      min_price: searchParams.get('min_price') || '',
      max_price: searchParams.get('max_price') || '',
      locations: readList(searchParams, 'location'),
      stars: readList(searchParams, 'star'),
      amenities: readList(searchParams, 'amenity'),
      room_type: searchParams.get('room_type') || '',
    }),
    [searchParams],
  )

  // The top search box is a *draft*; submitting it starts a clean new search so
  // stale filters (including `featured`) can never leak into it.
  const [draft, setDraft] = useState({
    search: query.search,
    check_in: query.check_in,
    check_out: query.check_out,
    guests: query.guests,
  })
  useEffect(
    () =>
      setDraft({
        search: query.search,
        check_in: query.check_in,
        check_out: query.check_out,
        guests: query.guests,
      }),
    [query.search, query.check_in, query.check_out, query.guests],
  )

  const [priceDraft, setPriceDraft] = useState({ min: query.min_price, max: query.max_price })
  useEffect(() => setPriceDraft({ min: query.min_price, max: query.max_price }), [query.min_price, query.max_price])

  /**
   * Update the querystring. Any filter change drops back to page 1 unless the
   * caller is explicitly paging (`keepPage`).
   */
  const applyParams = (mutate, { keepPage = false } = {}) => {
    const next = new URLSearchParams(searchParams)
    mutate(next)
    if (!keepPage) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  const setPage = (nextPage) =>
    applyParams((next) => {
      if (Number(nextPage) > 1) next.set('page', String(nextPage))
      else next.delete('page')
    }, { keepPage: true })

  const toggleListValue = (key, value) =>
    applyParams((next) => {
      const existing = next.getAll(key)
      next.delete(key)
      const updated = existing.includes(value)
        ? existing.filter((item) => item !== value)
        : [...existing, value]
      updated.forEach((item) => next.append(key, item))
    })

  const setValue = (key, value) =>
    applyParams((next) => {
      if (value) next.set(key, value)
      else next.delete(key)
    })

  const clearAll = () => setSearchParams(new URLSearchParams(), { replace: true })

  /** Start a fresh search: a clean URL with only the fields the visitor typed. */
  const submitSearch = (event) => {
    event.preventDefault()
    const next = new URLSearchParams()
    const search = draft.search.trim()
    if (search) next.set('search', search)
    if (draft.guests && Number(draft.guests) > 0) next.set('guests', String(Number(draft.guests)))
    if (draft.check_in) next.set('check_in', draft.check_in)
    if (draft.check_out) {
      if (draft.check_in && draft.check_out <= draft.check_in) {
        setSearchError('Check-out must be at least one night after check-in.')
        return
      }
      next.set('check_out', draft.check_out)
    }
    setSearchError('')
    setSearchParams(next, { replace: true })
  }

  // --- data -------------------------------------------------------------
  const apiParams = useMemo(
    () => ({
      search: query.search,
      check_in: query.check_in,
      check_out: query.check_out,
      guests: query.guests,
      featured: query.featured ? 'true' : '',
      sort: query.sort,
      min_price: query.min_price,
      max_price: query.max_price,
      city: query.locations.join(','),
      star_rating: query.stars,
      amenity: query.amenities,
      room_type: query.room_type,
      page,
      page_size: PAGE_SIZE,
    }),
    [query, page],
  )

  const { data, loading, error, reload } = useFetch((signal) => api.hotels.list(apiParams, { signal }), [apiParams])
  const { data: meta } = useFetch((signal) => api.hotels.filters({ signal }), [])

  const hotels = data?.results || []
  const pageCount = data?.num_pages || 1
  const count = data?.count ?? hotels.length
  const nights = nightsBetween(query.check_in, query.check_out)
  const destination = query.search || query.locations[0] || ''
  const empty = emptyState(data?.meta?.empty_reason, destination)

  const buildSearchString = () => {
    const params = new URLSearchParams()
    if (query.check_in) params.set('check_in', query.check_in)
    if (query.check_out) params.set('check_out', query.check_out)
    if (query.guests) params.set('guests', query.guests)
    return params.toString()
  }

  const activeChips = [
    ...query.locations.map((value) => ({ label: value, onRemove: () => toggleListValue('location', value) })),
    ...query.stars.map((value) => ({ label: `${value}+ stars`, onRemove: () => toggleListValue('star', value) })),
    ...query.amenities.map((value) => ({ label: value, onRemove: () => toggleListValue('amenity', value) })),
    ...(query.featured ? [{ label: 'Featured only', onRemove: () => setValue('featured', '') }] : []),
    ...(query.search ? [{ label: `“${query.search}”`, onRemove: () => setValue('search', '') }] : []),
    ...(query.min_price || query.max_price
      ? [{
          label: `${query.min_price || 0} – ${query.max_price || 'any'}`,
          onRemove: () => applyParams((next) => {
            next.delete('min_price')
            next.delete('max_price')
          }),
        }]
      : []),
  ]

  return (
    <>
      <section className="page-hero">
        <div className="container">
          <div className="breadcrumb">
            <span>Home</span>
            <span className="breadcrumb__sep">/</span>
            <span>Hotels</span>
          </div>
          <h1>{meta?.section?.heading || 'Hotels & Resorts'}</h1>
          <p>{meta?.section?.subheading || `Find the perfect stay for your next trip with ${title}.`}</p>

          <form className="row-center wrap" style={{ marginTop: 'var(--space-5)', gap: 'var(--space-3)' }} onSubmit={submitSearch}>
            <input
              className="input"
              style={{ maxWidth: 280, background: '#ffffff', color: 'var(--ink-900)' }}
              placeholder="Search hotels or destinations"
              value={draft.search}
              onChange={(event) => setDraft((current) => ({ ...current, search: event.target.value }))}
            />
            <label className="row-center" style={{ gap: 8, color: '#fff', fontSize: 'var(--text-sm)' }}>
              <Icon name="calendar" size={16} />
              <input
                type="date"
                className="input"
                style={{ maxWidth: 165, background: '#ffffff', color: 'var(--ink-900)' }}
                value={draft.check_in}
                onChange={(event) => setDraft((current) => ({ ...current, check_in: event.target.value }))}
              />
              <span>→</span>
              <input
                type="date"
                className="input"
                style={{ maxWidth: 165, background: '#ffffff', color: 'var(--ink-900)' }}
                min={draft.check_in}
                value={draft.check_out}
                onChange={(event) => setDraft((current) => ({ ...current, check_out: event.target.value }))}
              />
            </label>
            <label className="row-center" style={{ gap: 8, color: '#fff', fontSize: 'var(--text-sm)' }}>
              <Icon name="users" size={16} />
              <input
                type="number"
                min="1"
                max="12"
                step="1"
                inputMode="numeric"
                placeholder="Guests"
                className="input"
                style={{ maxWidth: 110, background: '#ffffff', color: 'var(--ink-900)' }}
                value={draft.guests}
                onChange={(event) => setDraft((current) => ({ ...current, guests: event.target.value }))}
              />
              {Number(draft.guests) > 0 ? (
                <span style={{ whiteSpace: 'nowrap' }}>
                  {suggestedRooms(draft.guests)} room{suggestedRooms(draft.guests) > 1 ? 's' : ''}
                </span>
              ) : null}
            </label>
            <button type="submit" className="btn btn--gold">
              <Icon name="search" size={16} />
              Search
            </button>
          </form>
          {searchError ? (
            <p className="tiny" style={{ marginTop: 8, color: '#ffd7d7' }} role="alert">
              {searchError}
            </p>
          ) : null}
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className="listing">
            {/* --- filter sidebar ------------------------------------- */}
            <aside className={`filters ${filtersOpen ? 'is-open' : ''}`.trim()}>
              <div className="filters__head">
                <h3 className="filters__title">
                  <Icon name="sliders" size={17} /> Filter by
                </h3>
                <button type="button" className="btn btn--ghost btn--sm" onClick={clearAll}>
                  Clear all
                </button>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Location</div>
                <div className="filters__scroll">
                  <label className="filters__option">
                    <input
                      type="checkbox"
                      checked={query.locations.length === 0}
                      onChange={() => applyParams((next) => next.delete('location'))}
                    />
                    All locations
                  </label>
                  {(meta?.locations || []).map((location) => (
                    <label key={location.label} className="filters__option">
                      <input
                        type="checkbox"
                        checked={query.locations.includes(location.city)}
                        onChange={() => toggleListValue('location', location.city)}
                      />
                      <span>{location.label}</span>
                      <span className="filters__count">{location.hotels}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Featured</div>
                <label className="filters__option">
                  <input
                    type="checkbox"
                    checked={query.featured}
                    onChange={(event) => setValue('featured', event.target.checked ? 'true' : '')}
                  />
                  <span>Featured hotels only</span>
                </label>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Price Range</div>
                <div className="filters__range">
                  <input
                    type="number"
                    className="input"
                    placeholder={meta?.price_range?.min || '0'}
                    value={priceDraft.min}
                    onChange={(event) => setPriceDraft((current) => ({ ...current, min: event.target.value }))}
                    onBlur={() => setValue('min_price', priceDraft.min)}
                  />
                  <span className="muted">—</span>
                  <input
                    type="number"
                    className="input"
                    placeholder={meta?.price_range?.max || '500'}
                    value={priceDraft.max}
                    onChange={(event) => setPriceDraft((current) => ({ ...current, max: event.target.value }))}
                    onBlur={() => setValue('max_price', priceDraft.max)}
                  />
                </div>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Hotel Type</div>
                {(meta?.star_ratings || [5, 4, 3]).map((star) => (
                  <label key={star} className="filters__option">
                    <input
                      type="checkbox"
                      checked={query.stars.includes(String(star))}
                      onChange={() => toggleListValue('star', String(star))}
                    />
                    <span>{star} Star</span>
                  </label>
                ))}
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Room Type</div>
                <select className="select" value={query.room_type} onChange={(event) => setValue('room_type', event.target.value)}>
                  <option value="">Any room type</option>
                  {(meta?.room_types || []).map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Amenities</div>
                <div className="filters__scroll">
                  {(meta?.amenities || []).map((amenity) => (
                    <label key={amenity.id} className="filters__option">
                      <input
                        type="checkbox"
                        checked={query.amenities.includes(amenity.name)}
                        onChange={() => toggleListValue('amenity', amenity.name)}
                      />
                      <span>{amenity.name}</span>
                      <span className="filters__count">{amenity.hotel_count}</span>
                    </label>
                  ))}
                </div>
              </div>

              <button type="button" className="btn btn--outline filters__reset" onClick={clearAll}>
                Clear Filters
              </button>
            </aside>

            {/* --- results -------------------------------------------- */}
            <div>
              <div className="listing__toolbar">
                <div className="row-center wrap" style={{ gap: 'var(--space-3)' }}>
                  <button
                    type="button"
                    className="btn btn--outline btn--sm listing__mobile-toggle"
                    onClick={() => setFiltersOpen((value) => !value)}
                  >
                    <Icon name="sliders" size={15} />
                    Filters
                  </button>
                  <span className="listing__count">
                    Showing <strong>{hotels.length}</strong> of <strong>{count}</strong>{' '}
                    {count === 1 ? 'hotel' : 'hotels'}
                    {nights > 0 ? ` · ${nights} night${nights === 1 ? '' : 's'}` : ''}
                  </span>
                </div>

                <label className="listing__sort">
                  <span className="muted">Sort by</span>
                  <select className="select" value={query.sort} onChange={(event) => setValue('sort', event.target.value)}>
                    {SORTS.map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {activeChips.length ? (
                <div className="filters__chips">
                  {activeChips.map((chip) => (
                    <span key={chip.label} className="filters__chip">
                      {chip.label}
                      <button type="button" onClick={chip.onRemove} aria-label={`Remove ${chip.label} filter`}>
                        <Icon name="close" size={13} />
                      </button>
                    </span>
                  ))}
                </div>
              ) : null}

              {error ? (
                <div className="alert alert--error" style={{ marginBottom: 'var(--space-5)' }}>
                  <Icon name="info" size={16} />
                  <span>{error.message}</span>
                  <button type="button" className="btn btn--ghost btn--sm" onClick={reload}>
                    Retry
                  </button>
                </div>
              ) : null}

              {loading ? (
                <SkeletonGrid count={6} columns={3} />
              ) : hotels.length ? (
                <div className="grid grid--3">
                  {hotels.map((hotel, index) => (
                    <Reveal key={hotel.id} delay={(index % 3) * 90}>
                      <HotelCard hotel={hotel} currency={currency} search={buildSearchString()} />
                    </Reveal>
                  ))}
                </div>
              ) : (
                <div className="empty">
                  <Icon name="search" size={32} className="empty__icon" />
                  <h3>{empty.title}</h3>
                  <p className="tiny">{empty.hint}</p>
                  <button type="button" className="btn btn--gold" onClick={clearAll}>
                    Clear all filters
                  </button>
                </div>
              )}

              <Pagination page={page} pageCount={pageCount} onChange={setPage} disabled={loading} />
            </div>
          </div>
        </div>
      </section>
    </>
  )
}
