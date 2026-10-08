import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import Icon from '../components/Icon'
import { SkeletonGrid } from '../components/Loader'
import OfferCard from '../components/OfferCard'
import Pagination from '../components/Pagination'
import Reveal from '../components/Reveal'
import { usePageMeta, useSite } from '../context/SiteContext'
import useFetch from '../hooks/useFetch'
import { nightsBetween } from '../utils/format'

const SORTS = [
  ['recommended', 'Recommended'],
  ['discount', 'Highest Discount'],
  ['price_low', 'Lowest Price'],
  ['price_high', 'Highest Price'],
  ['ending_soon', 'Ending Soon'],
  ['newest', 'Newest'],
]

const PAGE_SIZE = 9

function readList(params, key) {
  return params.getAll(key).filter(Boolean)
}

export default function Offers() {
  const { currency } = useSite()
  const [searchParams, setSearchParams] = useSearchParams()
  const [filtersOpen, setFiltersOpen] = useState(false)

  const page = Math.max(1, Number(searchParams.get('page')) || 1)

  const query = useMemo(
    () => ({
      search: searchParams.get('search') || '',
      category: searchParams.get('category') || '',
      destinations: readList(searchParams, 'destination'),
      offerTypes: readList(searchParams, 'offer_type'),
      roomTypes: readList(searchParams, 'room_type'),
      benefits: readList(searchParams, 'benefit'),
      discount: searchParams.get('discount') || '',
      min_price: searchParams.get('min_price') || '',
      max_price: searchParams.get('max_price') || '',
      check_in: searchParams.get('check_in') || '',
      check_out: searchParams.get('check_out') || '',
      guests: searchParams.get('guests') || '',
      sort: searchParams.get('sort') || 'recommended',
    }),
    [searchParams],
  )

  const [priceDraft, setPriceDraft] = useState({ min: query.min_price, max: query.max_price })
  useEffect(() => setPriceDraft({ min: query.min_price, max: query.max_price }), [query.min_price, query.max_price])

  const applyParams = (mutate, { keepPage = false } = {}) => {
    const next = new URLSearchParams(searchParams)
    mutate(next)
    if (!keepPage) next.delete('page')
    setSearchParams(next, { replace: true })
  }

  const setValue = (key, value) =>
    applyParams((next) => {
      if (value) next.set(key, value)
      else next.delete(key)
    })

  const toggleListValue = (key, value) =>
    applyParams((next) => {
      const existing = next.getAll(key)
      next.delete(key)
      const updated = existing.includes(value)
        ? existing.filter((item) => item !== value)
        : [...existing, value]
      updated.forEach((item) => next.append(key, item))
    })

  const setPage = (nextPage) =>
    applyParams((next) => {
      if (Number(nextPage) > 1) next.set('page', String(nextPage))
      else next.delete('page')
    }, { keepPage: true })

  const clearAll = () => setSearchParams(new URLSearchParams(), { replace: true })

  const hasFilters = Boolean(
    query.search || query.category || query.destinations.length || query.offerTypes.length ||
    query.roomTypes.length || query.benefits.length || query.discount ||
    query.min_price || query.max_price || query.check_in || query.check_out,
  )

  // --- data -------------------------------------------------------------
  const apiParams = useMemo(
    () => ({
      search: query.search,
      category: query.category,
      destination: query.destinations.join(','),
      offer_type: query.offerTypes.join(','),
      room_type: query.roomTypes.join(','),
      benefit: query.benefits,
      discount: query.discount,
      min_price: query.min_price,
      max_price: query.max_price,
      check_in: query.check_in,
      check_out: query.check_out,
      sort: query.sort,
      page,
      page_size: PAGE_SIZE,
    }),
    [query, page],
  )

  const { data: pageData } = useFetch((signal) => api.offers.page({ signal }), [])
  const { data: categoryData } = useFetch((signal) => api.offers.categories({ signal }), [])
  const { data: meta } = useFetch((signal) => api.offers.filters({ signal }), [])
  const { data, loading, error, reload } = useFetch((signal) => api.offers.list(apiParams, { signal }), [apiParams])

  const settings = pageData?.settings
  const featured = pageData?.featured || []
  const limited = pageData?.limited || []
  const categories = categoryData?.results || []
  const totalOffers = categoryData?.total ?? 0

  const offers = data?.results || []
  const pageCount = data?.num_pages || 1
  const count = data?.count ?? offers.length
  const nights = nightsBetween(query.check_in, query.check_out)

  usePageMeta({ title: settings?.seo_title, description: settings?.seo_description })

  const buildSearchString = () => {
    const params = new URLSearchParams()
    if (query.check_in) params.set('check_in', query.check_in)
    if (query.check_out) params.set('check_out', query.check_out)
    if (query.guests) params.set('guests', query.guests)
    return params.toString()
  }

  const heroStyle = settings?.hero_image
    ? { backgroundImage: `linear-gradient(rgba(6,21,38,.62), rgba(6,21,38,.72)), url(${settings.hero_image})` }
    : undefined

  return (
    <>
      {/* --- hero ------------------------------------------------------- */}
      {settings?.hero_enabled !== false ? (
        <section className={`offers-hero ${settings?.hero_image ? 'offers-hero--image' : ''}`.trim()} style={heroStyle}>
          <div className="container">
            <div className="breadcrumb">
              <Link to="/">Home</Link>
              <span className="breadcrumb__sep">/</span>
              <span>Offers</span>
            </div>
            <h1>{settings?.page_title || 'Offers & Deals'}</h1>
            <p>{settings?.page_description || 'Exclusive hotel deals and special rates for your next stay.'}</p>

            {settings?.hero_search_enabled !== false ? (
              <div className="offers-search">
                <label className="offers-search__field offers-search__field--grow">
                  <Icon name="search" size={16} />
                  <input
                    list="offer-destinations"
                    placeholder="Search offers or destinations"
                    value={query.search}
                    onChange={(event) => setValue('search', event.target.value)}
                  />
                  <datalist id="offer-destinations">
                    {(meta?.destinations || []).map((destination) => (
                      <option key={destination.label} value={destination.city} />
                    ))}
                  </datalist>
                </label>
                <label className="offers-search__field">
                  <Icon name="calendar" size={16} />
                  <input
                    type="date"
                    value={query.check_in}
                    onChange={(event) => setValue('check_in', event.target.value)}
                    aria-label="Check-in"
                  />
                </label>
                <label className="offers-search__field">
                  <Icon name="calendar" size={16} />
                  <input
                    type="date"
                    min={query.check_in}
                    value={query.check_out}
                    onChange={(event) => setValue('check_out', event.target.value)}
                    aria-label="Check-out"
                  />
                </label>
                <label className="offers-search__field offers-search__field--sm">
                  <Icon name="users" size={16} />
                  <input
                    type="number"
                    min="1"
                    max="12"
                    placeholder="Guests"
                    value={query.guests}
                    onChange={(event) => setValue('guests', event.target.value)}
                    aria-label="Guests"
                  />
                </label>
                <Link to="/offers" className="btn btn--gold" onClick={(event) => { event.preventDefault(); clearAll() }}>
                  Search
                </Link>
              </div>
            ) : null}
            {nights > 0 ? (
              <span className="offers-hero__note">
                Showing deals for {nights} night{nights === 1 ? '' : 's'}
              </span>
            ) : null}
          </div>
        </section>
      ) : null}

      {/* --- categories ------------------------------------------------- */}
      {categories.length ? (
        <section className="offers-categories">
          <div className="container">
            <div className="offers-chips" role="tablist" aria-label="Offer categories">
              <button
                type="button"
                className={`offers-chip ${!query.category ? 'is-active' : ''}`.trim()}
                onClick={() => setValue('category', '')}
              >
                All Offers
                <span className="offers-chip__count">{totalOffers}</span>
              </button>
              {categories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  className={`offers-chip ${query.category === category.slug ? 'is-active' : ''}`.trim()}
                  onClick={() => setValue('category', query.category === category.slug ? '' : category.slug)}
                >
                  {category.name}
                  {category.offer_count ? <span className="offers-chip__count">{category.offer_count}</span> : null}
                </button>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {/* --- featured --------------------------------------------------- */}
      {settings?.featured_enabled !== false && featured.length ? (
        <section className="section" style={{ paddingBottom: 0 }}>
          <div className="container">
            <div className="section-head">
              <div>
                <span className="section-head__eyebrow">
                  <Icon name="sparkles" size={14} /> Top picks
                </span>
                <h2>{settings?.featured_heading || 'Featured Offers'}</h2>
                <p className="muted">{settings?.featured_subheading || 'Handpicked deals for your next getaway'}</p>
              </div>
            </div>
            <div className="offers-featured">
              {featured.map((offer, index) => (
                <Reveal key={offer.id} delay={index * 80}>
                  <OfferCard offer={offer} currency={currency} />
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {/* --- limited time ---------------------------------------------- */}
      {settings?.limited_enabled !== false && limited.length ? (
        <section className="section" style={{ paddingBottom: 0 }}>
          <div className="container">
            <div className="section-head">
              <div>
                <span className="section-head__eyebrow section-head__eyebrow--hot">
                  <Icon name="clock" size={14} /> Ending soon
                </span>
                <h2>{settings?.limited_heading || 'Limited-Time Deals'}</h2>
                <p className="muted">{settings?.limited_subheading || 'Book before these offers expire.'}</p>
              </div>
            </div>
            <div className="grid grid--3">
              {limited.map((offer, index) => (
                <Reveal key={offer.id} delay={(index % 3) * 80}>
                  <OfferCard offer={offer} currency={currency} />
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {/* --- all offers ------------------------------------------------- */}
      <section className="section">
        <div className="container">
          <div className="section-head" style={{ marginBottom: 'var(--space-5)' }}>
            <div>
              <h2>All Offers</h2>
              <p className="muted">Browse every active deal and filter to find your perfect rate.</p>
            </div>
          </div>

          <div className="listing">
            {/* --- filters ------------------------------------------- */}
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
                <div className="filters__group-title">Offer Type</div>
                {(meta?.offer_types || []).map((type) => (
                  <label key={type.value} className="filters__option">
                    <input
                      type="checkbox"
                      checked={query.offerTypes.includes(type.value)}
                      onChange={() => toggleListValue('offer_type', type.value)}
                    />
                    <span>{type.label}</span>
                  </label>
                ))}
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Discount</div>
                {(meta?.discount_tiers || []).map((tier) => (
                  <label key={tier.value} className="filters__option">
                    <input
                      type="radio"
                      name="discount"
                      checked={query.discount === String(tier.value)}
                      onChange={() => setValue('discount', query.discount === String(tier.value) ? '' : String(tier.value))}
                    />
                    <span>{tier.label}</span>
                  </label>
                ))}
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Destination</div>
                <div className="filters__scroll">
                  {(meta?.destinations || []).map((destination) => (
                    <label key={destination.label} className="filters__option">
                      <input
                        type="checkbox"
                        checked={query.destinations.includes(destination.city)}
                        onChange={() => toggleListValue('destination', destination.city)}
                      />
                      <span>{destination.label}</span>
                      <span className="filters__count">{destination.hotels}</span>
                    </label>
                  ))}
                  {!meta?.destinations?.length ? <span className="tiny muted">No destinations yet.</span> : null}
                </div>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Room Type</div>
                <select
                  className="select"
                  value={query.roomTypes[0] || ''}
                  onChange={(event) => applyParams((next) => {
                    next.delete('room_type')
                    if (event.target.value) next.set('room_type', event.target.value)
                  })}
                >
                  <option value="">Any room type</option>
                  {(meta?.room_types || []).map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Price Range (per night)</div>
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
                    placeholder={meta?.price_range?.max || '0'}
                    value={priceDraft.max}
                    onChange={(event) => setPriceDraft((current) => ({ ...current, max: event.target.value }))}
                    onBlur={() => setValue('max_price', priceDraft.max)}
                  />
                </div>
              </div>

              <div className="filters__group">
                <div className="filters__group-title">Benefits</div>
                <div className="filters__scroll">
                  {(meta?.benefits || []).map((benefit) => (
                    <label key={benefit} className="filters__option">
                      <input
                        type="checkbox"
                        checked={query.benefits.includes(benefit)}
                        onChange={() => toggleListValue('benefit', benefit)}
                      />
                      <span>{benefit}</span>
                    </label>
                  ))}
                  {!meta?.benefits?.length ? <span className="tiny muted">No benefits yet.</span> : null}
                </div>
              </div>

              <button type="button" className="btn btn--outline filters__reset" onClick={clearAll}>
                Clear Filters
              </button>
            </aside>

            {/* --- results ------------------------------------------- */}
            <div>
              <div className="listing__toolbar">
                <div className="row-center wrap" style={{ gap: 'var(--space-3)' }}>
                  <button
                    type="button"
                    className="btn btn--outline btn--sm listing__mobile-toggle"
                    onClick={() => setFiltersOpen((value) => !value)}
                  >
                    <Icon name="sliders" size={15} /> Filters
                  </button>
                  <span className="listing__count">
                    Showing <strong>{offers.length}</strong> of <strong>{count}</strong> offers
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
              ) : offers.length ? (
                <div className="grid grid--3">
                  {offers.map((offer, index) => (
                    <Reveal key={offer.id} delay={(index % 3) * 80}>
                      <OfferCard offer={offer} currency={currency} />
                    </Reveal>
                  ))}
                </div>
              ) : hasFilters || totalOffers > 0 ? (
                <div className="empty">
                  <Icon name="tag" size={32} className="empty__icon" />
                  <h3>No offers match your filters</h3>
                  <p className="tiny">Try changing your dates or filters.</p>
                  <button type="button" className="btn btn--gold" onClick={clearAll}>
                    Clear Filters
                  </button>
                </div>
              ) : (
                <div className="empty">
                  <Icon name="tag" size={32} className="empty__icon" />
                  <h3>No offers available right now</h3>
                  <p className="tiny">We don&apos;t have any active deals matching your search.</p>
                  <Link to="/hotels" className="btn btn--gold">
                    Browse Hotels
                  </Link>
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
