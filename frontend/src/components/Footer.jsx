import { Link } from 'react-router-dom'

import { useSite } from '../context/SiteContext'
import Icon from './Icon'

const SOCIALS = [
  ['facebook_url', 'facebook', 'Facebook'],
  ['instagram_url', 'instagram', 'Instagram'],
  ['twitter_url', 'twitter', 'Twitter'],
  ['youtube_url', 'youtube', 'YouTube'],
]

export default function Footer() {
  const { settings, title, contactSettings, contactLocation } = useSite()
  const footerLinks = settings?.footer_links || []
  const legalLinks = settings?.legal_links || []
  const socials = SOCIALS.filter(([key]) => settings?.[key])

  // The footer reads the same Contact CMS data as the Contact page, so editing
  // one phone number updates both. Site settings remains the fallback for a
  // field the admin has left blank.
  const email = contactSettings?.email || settings?.contact_email
  const phone = contactSettings?.phone || settings?.contact_phone
  const address = contactLocation?.full_address || settings?.address

  return (
    <footer className="footer">
      <div className="container">
        <div className="footer__grid">
          <div>
            <div className="footer__brand">
              {settings?.logo_display ? (
                <img src={settings.logo_display} alt={title} />
              ) : (
                <>
                  <span className="header__brand-mark" aria-hidden="true">
                    <Icon name="compass" size={20} />
                  </span>
                  <span className="display" style={{ fontSize: '1.35rem', color: '#fff' }}>
                    {title}
                  </span>
                </>
              )}
            </div>
            <p style={{ fontSize: 'var(--text-sm)', maxWidth: '34ch' }}>
              {settings?.meta_description ||
                'Hand-picked hotels and resorts with honest pricing and instant confirmation.'}
            </p>
            {socials.length ? (
              <div className="footer__socials">
                {socials.map(([key, icon, label]) => (
                  <a
                    key={key}
                    href={settings[key]}
                    className="footer__social"
                    target="_blank"
                    rel="noreferrer noopener"
                    aria-label={label}
                  >
                    <Icon name={icon} size={17} />
                  </a>
                ))}
              </div>
            ) : null}
          </div>

          <div>
            <h4>Company</h4>
            <div className="footer__links">
              {footerLinks.length ? (
                footerLinks.map((link) => (
                  <Link key={link.id} to={link.url}>
                    {link.label}
                  </Link>
                ))
              ) : (
                <>
                  <Link to="/hotels">Hotels</Link>
                  <Link to="/offers">Special Offers</Link>
                  <Link to="/about">About Us</Link>
                </>
              )}
            </div>
          </div>

          <div>
            <h4>Support</h4>
            <div className="footer__links">
              <Link to="/contact">Contact Us</Link>
              <Link to="/dashboard">My Bookings</Link>
            </div>
          </div>

          <div>
            <h4>Get in touch</h4>
            <div className="footer__contact">
              {address ? (
                <span className="footer__contact-row">
                  <Icon name="map-pin" size={16} />
                  <span>{address}</span>
                </span>
              ) : null}
              {email ? (
                <a className="footer__contact-row" href={`mailto:${email}`}>
                  <Icon name="mail" size={16} />
                  <span>{email}</span>
                </a>
              ) : null}
              {phone ? (
                <a className="footer__contact-row" href={`tel:${phone.replace(/[^+0-9]/g, '')}`}>
                  <Icon name="phone" size={16} />
                  <span>{phone}</span>
                </a>
              ) : null}
            </div>
          </div>
        </div>

        <div className="footer__bottom">
          <span>{settings?.footer_text || `© ${new Date().getFullYear()} ${title}. All rights reserved.`}</span>
          <span className="footer__legal">
            {legalLinks.length ? (
              legalLinks.map((link) => (
                <Link key={link.id} to={link.url}>
                  {link.label}
                </Link>
              ))
            ) : (
              <>
                <Link to="/privacy">Privacy Policy</Link>
                <Link to="/terms">Terms of Service</Link>
                <Link to="/cookies">Cookie Policy</Link>
              </>
            )}
          </span>
        </div>
      </div>
    </footer>
  )
}
