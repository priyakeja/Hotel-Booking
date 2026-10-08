import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { useAuth } from '../context/AuthContext'
import { useSite } from '../context/SiteContext'
import { initials } from '../utils/format'
import Icon from './Icon'

/** Fallback navigation used until the CMS header links load. */
const DEFAULT_LINKS = [
  { id: 'home', label: 'Home', url: '/' },
  { id: 'hotels', label: 'Hotels', url: '/hotels' },
  { id: 'offers', label: 'Offers', url: '/offers' },
  { id: 'about', label: 'About', url: '/about' },
  { id: 'contact', label: 'Contact', url: '/contact' },
]

/**
 * Pick the single most specific link that matches the current location.
 *
 * React Router's `NavLink` only compares the pathname, so `/hotels?featured=true`
 * and `/hotels` both matched on the hotels page and underlined two links at once.
 * Matching the full `pathname + search` and preferring the longest match keeps
 * exactly one entry active.
 */
function activeLinkUrl(links, location) {
  const current = `${location.pathname}${location.search}`

  const matches = links.filter((link) => {
    const [path] = link.url.split('?')
    if (link.url.includes('?')) return link.url === current
    if (path === '/') return location.pathname === '/'
    return location.pathname === path || location.pathname.startsWith(`${path}/`)
  })

  // Longest URL wins so a query-specific link beats its plain-path sibling.
  return matches.sort((a, b) => b.url.length - a.url.length)[0]?.url || null
}

/** Brand lockup — uses the uploaded CMS logo when present, otherwise a wordmark. */
function Brand({ settings, title }) {
  const logo = settings?.logo_display

  return (
    <Link to="/" className="header__brand" aria-label={`${title} home`}>
      {logo ? (
        <img src={logo} alt={title} />
      ) : (
        <>
          <span className="header__brand-mark" aria-hidden="true">
            <Icon name="compass" size={21} />
          </span>
          <span className="header__brand-text">
            <span className="header__brand-title">{title}</span>
            {settings?.tagline ? <span className="header__brand-tag">{settings.tagline}</span> : null}
          </span>
        </>
      )}
    </Link>
  )
}

export default function Navbar() {
  const { settings, title } = useSite()
  const { user, isAuthenticated, logout } = useAuth()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setOpen(false), [location.pathname])

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const links = settings?.header_links?.length ? settings.header_links : DEFAULT_LINKS
  const activeUrl = useMemo(() => activeLinkUrl(links, location), [links, location])
  const dashboardPath = '/dashboard'

  return (
    <header className={`header ${scrolled ? 'is-scrolled' : ''}`.trim()}>
      <div className="container-wide">
        <div className="header__inner">
          <Brand settings={settings} title={title} />

          <nav className="header__nav" aria-label="Main navigation">
            {links.map((link) => (
              <Link
                key={link.id}
                to={link.url}
                className={`header__link ${link.url === activeUrl ? 'is-active' : ''}`.trim()}
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className="header__actions">
            {isAuthenticated ? (
              <>
                <Link to={dashboardPath} className="header__user">
                  {user?.avatar_display ? (
                    <img className="header__avatar" src={user.avatar_display} alt="" />
                  ) : (
                    <span className="header__avatar">{initials(user?.display_name || user?.username) || 'U'}</span>
                  )}
                  <span>{user?.first_name || user?.username}</span>
                </Link>
                <button type="button" className="btn btn--light btn--sm" onClick={logout}>
                  <Icon name="logout" size={15} />
                  <span>Logout</span>
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn btn--light btn--sm">
                  <Icon name="user" size={15} />
                  <span>Login</span>
                </Link>
                <Link to="/register" className="btn btn--gold btn--sm">
                  Sign Up
                </Link>
              </>
            )}

            <button
              type="button"
              className="header__toggle"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              aria-label="Toggle navigation menu"
            >
              <Icon name={open ? 'close' : 'menu'} size={20} />
            </button>
          </div>
        </div>

        <div className={`header__mobile ${open ? 'is-open' : ''}`.trim()}>
          {links.map((link) => (
            <Link
              key={`m-${link.id}`}
              to={link.url}
              className={`header__mobile-link ${link.url === activeUrl ? 'is-active' : ''}`.trim()}
            >
              {link.label}
            </Link>
          ))}
          {isAuthenticated ? (
            <Link to={dashboardPath} className="header__mobile-link">
              My Dashboard
            </Link>
          ) : (
            <>
              <Link to="/login" className="header__mobile-link">
                Login
              </Link>
              <Link to="/register" className="header__mobile-link">
                Create account
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
