import { Link } from 'react-router-dom'

import { api } from '../api/client'
import { useSite } from '../context/SiteContext'
import useFetch from '../hooks/useFetch'
import Icon from './Icon'

/** Split layout: CMS hero imagery on the left, form card on the right. */
export default function AuthLayout({ title, subtitle, children, asideTitle, asideText }) {
  const { settings, title: siteTitle } = useSite()
  const { data: heroes } = useFetch((signal) => api.site.heroes({ signal }), [])
  const heroImage = heroes?.[0]?.image

  return (
    <div className="auth-layout">
      <aside className="auth-aside">
        {heroImage ? <img src={heroImage} alt="" /> : null}
        <span className="eyebrow gold-text" style={{ marginBottom: 'var(--space-3)' }}>
          <Icon name="sparkles" size={15} />
          {heroes?.[0]?.eyebrow || 'Welcome back'}
        </span>
        <h2>{asideTitle || heroes?.[0]?.title || 'Discover your perfect stay'}</h2>
        <p>{asideText || heroes?.[0]?.subtitle || 'Sign in to manage bookings, save favourites and unlock member rates.'}</p>
      </aside>

      <div className="auth-panel">
        <div className="auth-card">
          <Link to="/" className="auth-card__brand">
            {settings?.logo_display ? (
              <img src={settings.logo_display} alt={siteTitle} style={{ height: 40 }} />
            ) : (
              <>
                <span className="auth-card__brand-mark">
                  <Icon name="compass" size={22} />
                </span>
                <span className="display" style={{ fontSize: '1.4rem' }}>
                  {siteTitle}
                </span>
              </>
            )}
          </Link>

          <h1>{title}</h1>
          {subtitle ? <p className="muted">{subtitle}</p> : null}

          {children}
        </div>
      </div>
    </div>
  )
}
