import { Link } from 'react-router-dom'

import { api } from '../api/client'
import Icon from '../components/Icon'
import { Loader } from '../components/Loader'
import Reveal from '../components/Reveal'
import useFetch from '../hooks/useFetch'

const PAGES = {
  about: {
    key: 'about',
    breadcrumb: 'About',
    title: 'About us',
    fallback:
      'Tell your story here. This page is powered by the “About” text section in the Django admin — add a heading, body copy and gallery images to publish it.',
  },
  privacy: {
    key: 'privacy',
    breadcrumb: 'Privacy Policy',
    title: 'Privacy Policy',
    fallback:
      'Publish this policy from the Django admin: create the “Privacy policy page” text section and its content appears here.',
  },
  terms: {
    key: 'terms',
    breadcrumb: 'Terms of Service',
    title: 'Terms of Service',
    fallback:
      'Publish these terms from the Django admin: create the “Terms of service page” text section and its content appears here.',
  },
  cookies: {
    key: 'cookies',
    breadcrumb: 'Cookie Policy',
    title: 'Cookie Policy',
    fallback:
      'Publish this policy from the Django admin: create the “Cookie policy page” text section and its content appears here.',
  },
}

export default function ContentPage({ page }) {
  const config = PAGES[page] || PAGES.about
  const { data: section, loading } = useFetch((signal) => api.site.section(config.key, { signal }), [config.key])

  const bodyContent = section?.body ? (
    section.body.split('\n\n').map((paragraph) => (
      <p key={paragraph.slice(0, 40)} className="muted">
        {paragraph}
      </p>
    ))
  ) : (
    <div className="alert alert--info">
      <Icon name="info" size={16} />
      <span>{config.fallback}</span>
    </div>
  )

  return (
    <>
      <section className="page-hero">
        <div className="container">
          <div className="breadcrumb">
            <Link to="/">Home</Link>
            <span className="breadcrumb__sep">/</span>
            <span>{config.breadcrumb}</span>
          </div>
          <h1>{section?.heading || config.title}</h1>
          {section?.subheading ? <p>{section.subheading}</p> : null}
        </div>
      </section>

      <section className="section">
        <div className="container">
          {loading ? <Loader label="Loading content…" /> : null}

          {!loading ? (
            <>
              {section?.image ? (
                <div className="content-split">
                  <Reveal variant="left" className="content-split__body">
                    <div className="prose">{bodyContent}</div>
                  </Reveal>
                  <Reveal variant="right" delay={120} className="content-split__media">
                    <img src={section.image} alt={section.heading} />
                  </Reveal>
                </div>
              ) : (
                <div className="prose">{bodyContent}</div>
              )}

              {section?.gallery?.length ? (
                <div className="grid grid--4" style={{ marginTop: 'var(--space-8)' }}>
                  {section.gallery.map((image) => (
                    <img
                      key={image.id}
                      src={image.image}
                      alt={image.alt_text || image.title}
                      loading="lazy"
                      style={{ aspectRatio: '1', objectFit: 'cover', borderRadius: 'var(--radius-sm)' }}
                    />
                  ))}
                </div>
              ) : null}
            </>
          ) : null}

          <div className="row-center wrap" style={{ marginTop: 'var(--space-7)', gap: 'var(--space-3)' }}>
            <Link to="/hotels" className="btn btn--gold">
              Browse hotels
            </Link>
            <Link to="/contact" className="btn btn--outline">
              Contact support
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}
