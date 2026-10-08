import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import AvailabilityChecker from '../components/AvailabilityChecker'
import Gallery from '../components/Gallery'
import Icon from '../components/Icon'
import { Loader } from '../components/Loader'
import Modal from '../components/Modal'
import Reveal from '../components/Reveal'
import RoomCard from '../components/RoomCard'
import StarRating from '../components/StarRating'
import { useAuth } from '../context/AuthContext'
import { useSite } from '../context/SiteContext'
import useFetch from '../hooks/useFetch'
import { formatDate, formatMoney, initials, nightsBetween } from '../utils/format'
import { resolveGallery } from '../utils/images'

const TABS = [
  ['overview', 'Overview'],
  ['rooms', 'Rooms'],
  ['amenities', 'Amenities'],
  ['reviews', 'Reviews'],
]

export default function HotelDetail() {
  const { slug } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { currency } = useSite()
  const { isAuthenticated } = useAuth()

  const [tab, setTab] = useState('overview')
  // The Book Now button jumps the visitor down to the room list, so anchor it here.
  const bodyRef = useRef(null)
  const [activeRoom, setActiveRoom] = useState(null)
  const [reviewForm, setReviewForm] = useState({ rating: 5, title: '', comment: '' })
  const [reviewState, setReviewState] = useState({ saving: false, error: null, done: false })

  const query = useMemo(
    () => ({
      check_in: searchParams.get('check_in') || '',
      check_out: searchParams.get('check_out') || '',
      guests: searchParams.get('guests') || '',
    }),
    [searchParams],
  )

  const searchString = useMemo(() => {
    const params = new URLSearchParams()
    if (query.check_in) params.set('check_in', query.check_in)
    if (query.check_out) params.set('check_out', query.check_out)
    if (query.guests) params.set('guests', query.guests)
    return params.toString()
  }, [query])

  const roomParams = useMemo(() => ({
    check_in: query.check_in,
    check_out: query.check_out,
  }), [query])

  const { data: hotel, loading, error, reload } = useFetch(
    (signal) => api.hotels.detail(slug, roomParams, { signal }),
    [slug, roomParams],
  )
  const { data: reviewData, reload: reloadReviews } = useFetch(
    (signal) => api.reviews.list({ hotel: slug, page_size: 12 }, { signal }),
    [slug],
  )

  useEffect(() => {
    if (hotel?.rooms?.length) {
      const requested = searchParams.get('room')
      setActiveRoom(hotel.rooms.find((room) => String(room.id) === requested) || null)
    }
  }, [hotel, searchParams])

  const rooms = hotel?.rooms || []
  const reviews = reviewData?.results || reviewData || []
  const nights = nightsBetween(query.check_in, query.check_out)
  const galleryCount = resolveGallery(hotel?.images, hotel?.image, hotel?.name).length

  const submitReview = async (event) => {
    event.preventDefault()
    setReviewState({ saving: true, error: null, done: false })
    try {
      await api.reviews.create({
        hotel: hotel.id,
        rating: Number(reviewForm.rating),
        title: reviewForm.title,
        comment: reviewForm.comment,
      })
      setReviewForm({ rating: 5, title: '', comment: '' })
      setReviewState({ saving: false, error: null, done: true })
      reloadReviews()
      reload()
    } catch (requestError) {
      setReviewState({ saving: false, error: requestError.message, done: false })
    }
  }

  if (loading && !hotel) {
    return (
      <div className="container section">
        <Loader label="Loading hotel details…" />
      </div>
    )
  }

  if (error || !hotel) {
    return (
      <div className="container section">
        <div className="empty">
          <Icon name="building" size={34} className="empty__icon" />
          <h3>We couldn&apos;t find that hotel</h3>
          <p className="tiny">{error?.message || 'It may have been unpublished.'}</p>
          <Link to="/hotels" className="btn btn--gold">
            Back to all hotels
          </Link>
        </div>
      </div>
    )
  }

  return (
    <>
      <section className="section-tight" style={{ background: 'var(--surface)' }}>
        <div className="container">
          <div className="breadcrumb">
            <Link to="/">Home</Link>
            <span className="breadcrumb__sep">/</span>
            <Link to="/hotels">Hotels</Link>
            <span className="breadcrumb__sep">/</span>
            <span>{hotel.name}</span>
          </div>

          <Reveal>
            <Gallery
              images={hotel.images}
              cover={hotel.image}
              title={hotel.name}
              badge={<span className="badge badge--glass">{galleryCount} photos</span>}
            />
          </Reveal>

          <div className="detail-head">
            <div>
              <h1 className="detail-head__title">{hotel.name}</h1>
              <span className="detail-head__location">
                <Icon name="map-pin" size={16} />
                {hotel.location}
              </span>
              <div className="detail-head__meta">
                <StarRating value={hotel.rating} count={hotel.review_count} />
                <span className="badge badge--navy">
                  <Icon name="building" size={13} />
                  {hotel.star_rating ? `${Number(hotel.star_rating).toFixed(1)} star` : 'Boutique'}
                </span>
                <span className="badge">
                  <Icon name="bed" size={13} />
                  {rooms.length} room type{rooms.length === 1 ? '' : 's'}
                </span>
              </div>
              {hotel.address ? (
                <p className="muted tiny" style={{ marginTop: 'var(--space-3)' }}>
                  {hotel.address}
                </p>
              ) : null}
            </div>

            <div className="detail-cta">
              <span className="tiny muted">From</span>
              <span className="detail-cta__price">
                <span className="price__amount">{formatMoney(hotel.price_per_night, currency)}</span>
                <span className="price__unit">/ night</span>
              </span>
              <button
                type="button"
                className="btn btn--gold"
                onClick={() => {
                  setTab('rooms')
                  bodyRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
                }}
              >
                <Icon name="calendar-check" size={16} />
                Book Now
              </button>
              <span className="detail-cta__meta">
                {nights > 0 ? `${nights} night stay selected` : 'Free cancellation up to 24h before check-in'}
              </span>
            </div>
          </div>
        </div>
      </section>

      <section ref={bodyRef} className="section detail-body" style={{ paddingTop: 0 }}>
        <div className="container">
          <div className="tabs" role="tablist">
            {TABS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                className={`tab ${tab === value ? 'is-active' : ''}`.trim()}
                onClick={() => setTab(value)}
              >
                {label}
                {value === 'rooms' ? ` (${rooms.length})` : ''}
                {value === 'reviews' ? ` (${hotel.review_count})` : ''}
              </button>
            ))}
          </div>

          {tab === 'overview' ? (
            <div className="detail-panels">
              <div>
                <div className="panel">
                  <h3 className="panel__title">About This Hotel</h3>
                  <p className="muted">{hotel.description || hotel.short_description}</p>
                </div>

                <div className="panel">
                  <h3 className="panel__title">Available Rooms</h3>
                  {rooms.length ? (
                    <div className="stack" style={{ gap: 'var(--space-4)' }}>
                      {rooms.map((room) => (
                        <RoomCard
                          key={room.id}
                          room={room}
                          hotelSlug={hotel.slug}
                          currency={currency}
                          search={searchString}
                          onCheckAvailability={(selected) => {
                            setActiveRoom(selected)
                            setTab('rooms')
                          }}
                        />
                      ))}
                    </div>
                  ) : (
                    <p className="muted">No rooms have been published for this hotel yet.</p>
                  )}
                </div>
              </div>

              <aside>
                <div className="panel">
                  <h3 className="panel__title">Hotel Highlights</h3>
                  <ul className="highlight-list">
                    {(hotel.highlights || []).map((item) => (
                      <li key={item}>
                        <Icon name="check" size={15} />
                        <span>{item}</span>
                      </li>
                    ))}
                    {!hotel.highlights?.length ? <li className="muted">Highlights coming soon.</li> : null}
                  </ul>
                </div>

                <div className="panel">
                  <h3 className="panel__title">Facilities</h3>
                  <div className="amenity-inline">
                    {(hotel.amenities || []).map((amenity) => (
                      <span key={amenity.id} className="amenity-inline__item">
                        <Icon name={amenity.icon} size={13} />
                        {amenity.name}
                      </span>
                    ))}
                  </div>
                </div>

                {hotel.nearby_facilities?.length ? (
                  <div className="panel">
                    <h3 className="panel__title">Nearby Facilities</h3>
                    <ul className="highlight-list">
                      {hotel.nearby_facilities.map((fac) => (
                        <li key={fac.id || fac.name}>
                          <Icon name={fac.icon || 'map-pin'} size={15} />
                          <div>
                            <strong>{fac.name}</strong> ({fac.distance_km} km)
                            {fac.category ? <span className="muted tiny" style={{ display: 'block' }}>{fac.category}</span> : null}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}


                <div className="panel" style={{ background: 'var(--gold-100)', borderColor: 'var(--gold-300)' }}>
                  <h3 className="panel__title">Need help booking?</h3>
                  <p className="tiny" style={{ marginBottom: 'var(--space-3)' }}>
                    Our team is available 24/7 to help with group bookings and special requests.
                  </p>
                  <Link to="/contact" className="btn btn--outline btn--sm">
                    Contact support
                  </Link>
                </div>
              </aside>
            </div>
          ) : null}

          {tab === 'rooms' ? (
            <div className="detail-panels">
              <div>
                {rooms.length ? (
                  <div className="stack" style={{ gap: 'var(--space-4)' }}>
                    {rooms.map((room) => (
                      <RoomCard
                        key={room.id}
                        room={room}
                        hotelSlug={hotel.slug}
                        currency={currency}
                        search={searchString}
                        onCheckAvailability={setActiveRoom}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty">
                    <Icon name="bed" size={30} className="empty__icon" />
                    <p>No rooms published yet.</p>
                  </div>
                )}
              </div>

              <aside>
                <div className="panel">
                  <h3 className="panel__title">Check Availability</h3>
                  {activeRoom ? (
                    <>
                      <p className="tiny muted" style={{ marginBottom: 'var(--space-4)' }}>
                        {activeRoom.name}
                      </p>
                      <AvailabilityChecker
                        room={activeRoom}
                        defaults={query}
                        currency={currency}
                        onProceed={(quote) =>
                          navigate(
                            `/hotels/${hotel.slug}/book?room=${activeRoom.id}&check_in=${quote.check_in}&check_out=${quote.check_out}&guests=${quote.guests}&rooms=${quote.rooms}`,
                          )
                        }
                      />
                    </>
                  ) : (
                    <p className="muted tiny">
                      Select a room to check live availability and get an instant price breakdown.
                    </p>
                  )}
                </div>
              </aside>
            </div>
          ) : null}

          {tab === 'amenities' ? (
            <div className="panel">
              <h3 className="panel__title">Amenities at {hotel.name}</h3>
              <div className="grid grid--3">
                {(hotel.amenities || []).map((amenity) => (
                  <div key={amenity.id} className="feature">
                    <span className="icon-tile">
                      <Icon name={amenity.icon} size={20} />
                    </span>
                    <div>
                      <h4 className="feature__title">{amenity.name}</h4>
                      {amenity.description ? <p className="feature__desc">{amenity.description}</p> : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {tab === 'reviews' ? (
            <div className="detail-panels">
              <div>
                <div className="review-list">
                  {reviews.length ? (
                    reviews.map((review) => (
                      <Reveal key={review.id}>
                        <article className="review">
                          <div className="review__head">
                            {review.author_avatar ? (
                              <img className="review__avatar" src={review.author_avatar} alt="" loading="lazy" />
                            ) : (
                              <span className="review__avatar review__avatar--fallback">
                                {initials(review.author_name)}
                              </span>
                            )}
                            <div>
                              <div className="review__name">{review.author_name}</div>
                              <div className="review__date">{formatDate(review.created_at)}</div>
                            </div>
                            <div className="grow" />
                            <StarRating value={review.rating} showValue={false} size={13} />
                          </div>
                          {review.title ? <h4 className="review__title">{review.title}</h4> : null}
                          <p className="review__body">{review.comment}</p>
                        </article>
                      </Reveal>
                    ))
                  ) : (
                    <div className="empty">
                      <Icon name="star" size={28} className="empty__icon" />
                      <p>No reviews yet — be the first to share your experience.</p>
                    </div>
                  )}
                </div>
              </div>

              <aside>
                <div className="panel">
                  <h3 className="panel__title">Write a review</h3>
                  {isAuthenticated ? (
                    <form onSubmit={submitReview}>
                      <label className="field">
                        <span className="field__label">Rating</span>
                        <select
                          className="select"
                          value={reviewForm.rating}
                          onChange={(event) => setReviewForm((current) => ({ ...current, rating: event.target.value }))}
                        >
                          {[5, 4, 3, 2, 1].map((value) => (
                            <option key={value} value={value}>
                              {value} star{value > 1 ? 's' : ''}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span className="field__label">Title</span>
                        <input
                          className="input"
                          value={reviewForm.title}
                          onChange={(event) => setReviewForm((current) => ({ ...current, title: event.target.value }))}
                          placeholder="Summarise your stay"
                        />
                      </label>
                      <label className="field">
                        <span className="field__label">Your review</span>
                        <textarea
                          className="textarea"
                          required
                          value={reviewForm.comment}
                          onChange={(event) => setReviewForm((current) => ({ ...current, comment: event.target.value }))}
                          placeholder="What stood out during your stay?"
                        />
                      </label>

                      {reviewState.error ? <div className="alert alert--error">{reviewState.error}</div> : null}
                      {reviewState.done ? (
                        <div className="alert alert--success">Thanks! Your review is published.</div>
                      ) : null}

                      <button type="submit" className="btn btn--gold btn--block" disabled={reviewState.saving}>
                        {reviewState.saving ? 'Publishing…' : 'Submit review'}
                      </button>
                    </form>
                  ) : (
                    <>
                      <p className="tiny muted">Sign in to share your experience with other travellers.</p>
                      <Link to="/login" className="btn btn--outline btn--block">
                        Sign in to review
                      </Link>
                    </>
                  )}
                </div>

              </aside>
            </div>
          ) : null}
        </div>
      </section>

      <Modal
        open={Boolean(activeRoom) && tab !== 'rooms'}
        onClose={() => setActiveRoom(null)}
        title={activeRoom ? `Check availability — ${activeRoom.name}` : ''}
      >
        {activeRoom ? (
          <AvailabilityChecker
            room={activeRoom}
            defaults={query}
            currency={currency}
            onProceed={(quote) =>
              navigate(
                `/hotels/${hotel.slug}/book?room=${activeRoom.id}&check_in=${quote.check_in}&check_out=${quote.check_out}&guests=${quote.guests}&rooms=${quote.rooms}`,
              )
            }
          />
        ) : null}
      </Modal>

    </>
  )
}
