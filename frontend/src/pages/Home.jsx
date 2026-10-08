import { Link } from 'react-router-dom'

import { api } from '../api/client'
import { AmenityGrid, FeatureStrip } from '../components/AmenityGrid'
import HotelCard from '../components/HotelCard'
import Icon from '../components/Icon'
import OfferCard from '../components/OfferCard'
import { Loader, SkeletonGrid } from '../components/Loader'
import Reveal from '../components/Reveal'
import SearchBar from '../components/SearchBar'
import TestimonialList from '../components/TestimonialList'
import { useSite } from '../context/SiteContext'
import useFetch from '../hooks/useFetch'

/** Renders a CMS text section, falling back to sensible defaults. */
function SectionHead({ section, fallbackTitle, fallbackSubtitle, action }) {
  return (
    <div className="section-head">
      <div>
        {section?.eyebrow ? <span className="section-head__eyebrow">{section.eyebrow}</span> : null}
        <h2>{section?.heading || fallbackTitle}</h2>
        {(section?.subheading || fallbackSubtitle) && (
          <p className="muted" style={{ maxWidth: '58ch' }}>
            {section?.subheading || fallbackSubtitle}
          </p>
        )}
      </div>
      {action}
    </div>
  )
}

export default function Home() {
  const { currency, title } = useSite()
  const { data, loading, error, reload } = useFetch((signal) => api.site.home({ signal }), [])
  // Real destinations power the search bar's suggestions (same source as the listing filters).
  const { data: filters } = useFetch((signal) => api.hotels.filters({ signal }), [])
  // Live featured deals — same data source as the Offers page, never hard-coded.
  const { data: offersData } = useFetch((signal) => api.offers.featured({ signal }), [])

  if (loading && !data) {
    return (
      <div className="container section">
        <Loader label="Loading homepage content…" />
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="container section">
        <div className="alert alert--error">
          <Icon name="info" size={17} />
          <span>{error.message}</span>
        </div>
        <button type="button" className="btn btn--gold" style={{ marginTop: 'var(--space-4)' }} onClick={reload}>
          Try again
        </button>
      </div>
    )
  }

  const hero = data?.heroes?.[0]
  const sections = data?.sections || {}
  const featured = data?.featured_hotels || []
  const avgRating = Number(data?.stats?.avg_rating) || 0
  const reviewCount = Number(data?.stats?.reviews) || 0
  const amenities = data?.amenities || []
  const testimonials = data?.testimonials || []
  const about = sections.about
  const cta = sections.cta
  const featuredOffers = offersData?.results || []

  return (
    <>
      {/* --- hero ------------------------------------------------------- */}
      <section className="hero">
        {hero?.image ? (
          <div className="hero__media">
            <img src={hero.image} alt="" />
          </div>
        ) : null}
        <div className="hero__overlay" style={{ '--hero-overlay': hero?.overlay_opacity ?? 0.6 }} />

        <div className="container">
          <div className="hero__inner">
            {hero?.eyebrow ? (
              <span className="hero__eyebrow eyebrow">
                <Icon name="sparkles" size={15} />
                {hero.eyebrow}
              </span>
            ) : null}

            <h1 className="hero__title">{hero?.title || `Welcome to ${title}`}</h1>

            {hero?.subtitle || hero?.description ? (
              <p className="hero__subtitle">{hero.subtitle || hero.description}</p>
            ) : null}

            <div className="hero__actions">
              <Link to={hero?.cta_link || '/hotels'} className="btn btn--gold btn--lg">
                {hero?.cta_text || 'Explore hotels'}
                <Icon name="arrow-right" size={17} />
              </Link>
              {hero?.secondary_cta_text ? (
                <Link to={hero.secondary_cta_link || '/hotels'} className="btn btn--light btn--lg">
                  {hero.secondary_cta_text}
                </Link>
              ) : null}
            </div>

            <div className="hero__stats">
              <div>
                <div className="hero__stat-value">{data?.stats?.hotels ?? 0}+</div>
                <div className="hero__stat-label">Hotels</div>
              </div>
              <div>
                <div className="hero__stat-value">{data?.stats?.destinations ?? 0}+</div>
                <div className="hero__stat-label">Destinations</div>
              </div>
              {avgRating > 0 ? (
                <div>
                  <div className="hero__stat-value">{avgRating.toFixed(1)}/5</div>
                  <div className="hero__stat-label">Guest rating</div>
                </div>
              ) : reviewCount > 0 ? (
                <div>
                  <div className="hero__stat-value">{reviewCount}+</div>
                  <div className="hero__stat-label">Guest reviews</div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      {/* --- search ----------------------------------------------------- */}
      <section className="container">
        <SearchBar locations={filters?.locations || []} />
      </section>

      {/* --- trust strip ------------------------------------------------ */}
      <section className="container home__features">
        <FeatureStrip features={data?.features || []} />
      </section>

      {/* --- featured hotels ------------------------------------------- */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="container">
          <SectionHead
            section={sections.featured_hotels}
            fallbackTitle="Featured Hotels"
            fallbackSubtitle="Handpicked hotels for your perfect getaway"
            action={
              <Link to={sections.featured_hotels?.cta_link || '/hotels'} className="link-more">
                {sections.featured_hotels?.cta_text || 'View All Hotels'}
                <Icon name="arrow-right" size={16} />
              </Link>
            }
          />

          {loading && !featured.length ? (
            <SkeletonGrid count={4} columns={4} />
          ) : (
            <div className="grid grid--4">
              {featured.slice(0, 4).map((hotel, index) => (
                <Reveal key={hotel.id} delay={index * 90}>
                  <HotelCard hotel={hotel} currency={currency} />
                </Reveal>
              ))}
            </div>
          )}

          {!featured.length && !loading ? (
            <div className="empty">
              <Icon name="building" size={30} className="empty__icon" />
              <p>No hotels have been published yet.</p>
              <p className="tiny">Add hotels in the Django admin and they appear here instantly.</p>
            </div>
          ) : null}
        </div>
      </section>

      {/* --- special offers (dynamic featured deals) ------------------- */}
      {featuredOffers.length ? (
        <section className="section" style={{ background: 'var(--surface-2)' }}>
          <div className="container">
            <SectionHead
              fallbackTitle="Special Offers"
              fallbackSubtitle="Save more on your next stay"
              action={
                <Link to="/offers" className="link-more">
                  View all offers
                  <Icon name="arrow-right" size={16} />
                </Link>
              }
            />
            <div className="grid grid--3">
              {featuredOffers.slice(0, 3).map((offer, index) => (
                <Reveal key={offer.id} delay={index * 90}>
                  <OfferCard offer={offer} currency={currency} />
                </Reveal>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {/* --- amenities -------------------------------------------------- */}
      {amenities.length ? (
        <section className="section section-navy">
          <div className="container">
            <div className="section-head" style={{ justifyContent: 'center', textAlign: 'center', flexDirection: 'column', alignItems: 'center' }}>
              <div>
                <h2>{sections.amenities?.heading || 'Our Amenities'}</h2>
                <p style={{ color: 'rgba(233,240,247,.78)' }}>
                  {sections.amenities?.subheading || 'Everything you need for a comfortable stay'}
                </p>
              </div>
            </div>
            <AmenityGrid amenities={amenities} />
          </div>
        </section>
      ) : null}

      {/* --- about band ------------------------------------------------- */}
      {about ? (
        <section className="section">
          <div className="container">
            <div className="about-band">
              <Reveal variant="left">
                <span className="section-head__eyebrow">{about.eyebrow || 'Why SkyStay'}</span>
                <h2>{about.heading}</h2>
                {about.subheading ? <p className="gold-text" style={{ fontWeight: 600 }}>{about.subheading}</p> : null}
                <p className="muted">{about.body}</p>

                {about.cta_text ? (
                  <Link to={about.cta_link || '/hotels'} className="btn btn--gold">
                    {about.cta_text}
                    <Icon name="arrow-right" size={16} />
                  </Link>
                ) : null}
              </Reveal>

              <Reveal variant="right" delay={120}>
                {about.image ? (
                  <div className="about-band__media">
                    <img src={about.image} alt={about.heading} />
                    <div className="about-band__stat">
                      <strong>{data?.stats?.destinations ?? 0}</strong>
                      <span className="tiny muted">Destinations covered</span>
                    </div>
                  </div>
                ) : null}

                {about.gallery?.length ? (
                  <div className="about-band__gallery">
                    {about.gallery.slice(0, 4).map((image) => (
                      <img key={image.id} src={image.image} alt={image.alt_text || image.title} loading="lazy" />
                    ))}
                  </div>
                ) : null}
              </Reveal>
            </div>
          </div>
        </section>
      ) : null}

      {/* --- testimonials ---------------------------------------------- */}
      {testimonials.length ? (
        <section className="section" style={{ background: 'var(--surface-2)' }}>
          <div className="container">
            <SectionHead
              section={sections.testimonials}
              fallbackTitle="What Our Guests Say"
              fallbackSubtitle="Real experiences from our valued guests."
            />
            <TestimonialList testimonials={testimonials} />
          </div>
        </section>
      ) : null}

      {/* --- CTA band --------------------------------------------------- */}
      {cta ? (
        <section className="section">
          <div className="container">
            <Reveal variant="zoom">
              <div className="cta-band">
                {cta.eyebrow ? <span className="section-head__eyebrow">{cta.eyebrow}</span> : null}
                <h2>{cta.heading}</h2>
                {cta.subheading ? <p>{cta.subheading}</p> : null}
                <div className="cta-band__actions">
                  <Link to={cta.cta_link || '/register'} className="btn btn--gold btn--lg">
                    {cta.cta_text || 'Get started'}
                  </Link>
                  <Link to="/hotels" className="btn btn--light btn--lg">
                    Browse hotels
                  </Link>
                </div>
              </div>
            </Reveal>
          </div>
        </section>
      ) : null}
    </>
  )
}
