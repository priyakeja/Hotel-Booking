import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import Icon from '../components/Icon'
import { Loader } from '../components/Loader'
import Reveal from '../components/Reveal'
import { usePageMeta, useSite } from '../context/SiteContext'
import { useToast } from '../context/ToastContext'
import { getDirectionsUrl, getEmbedMapUrl, getMapUrl } from '../utils/maps'

const EMPTY_FORM = { name: '', email: '', phone: '', booking_reference: '', subject: '', message: '' }
// Visual order of the form fields, used to pick which error to focus first.
const FIELD_ORDER = ['name', 'email', 'phone', 'booking_reference', 'subject', 'message']
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const REFERENCE_RE = /^[A-Za-z0-9][A-Za-z0-9\-_/]*$/
// Mobile numbers are exactly 10 digits (mirrors the backend rule).
const MOBILE_RE = /^\d{10}$/
const NAME_MIN = 3

/** Strips spaces/dashes and an optional +91 / 0 prefix so any format is accepted. */
function normaliseMobile(value) {
  const digits = String(value || '').replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('91')) return digits.slice(2)
  if (digits.length === 11 && digits.startsWith('0')) return digits.slice(1)
  return digits
}

/** Resolve a contact card into the link it should actually open. */
function cardAction(card, settings) {
  const location = settings.location
  if (card.kind === 'email' && settings.email) {
    return {
      href: `mailto:${settings.email}`,
      label: card.cta_label || settings.email,
      external: false,
    }
  }
  if (card.kind === 'phone' && settings.phone) {
    // Strip separators so mobile dialers recognise the number.
    return {
      href: `tel:${settings.phone.replace(/[^+0-9]/g, '')}`,
      label: card.cta_label || settings.phone,
      external: false,
    }
  }
  if (card.kind === 'location') {
    const href = getMapUrl(location)
    return href
      ? { href, label: card.cta_label || 'View on Map', external: true }
      : null
  }
  if (card.kind === 'custom' && card.cta_link) {
    return {
      href: card.cta_link,
      label: card.cta_label || 'Learn more',
      external: /^https?:/i.test(card.cta_link),
    }
  }
  return null
}

/** One contact card: icon, title, description and its dynamic action link. */
function ContactCard({ card, settings }) {
  const action = cardAction(card, settings)

  return (
    <div className="contact-card">
      <span className="icon-tile" aria-hidden="true">
        <Icon name={card.icon} size={20} />
      </span>
      <h3>{card.title}</h3>

      {/* The location card shows the live address rather than a blurb. */}
      {card.kind === 'location' ? (
        settings.location.full_address ? (
          <p className="muted tiny">{settings.location.full_address}</p>
        ) : (
          <p className="muted tiny">Address not configured yet.</p>
        )
      ) : card.description ? (
        <p className="muted tiny">{card.description}</p>
      ) : null}

      {action ? (
        action.external ? (
          <a
            className="link-more"
            href={action.href}
            target="_blank"
            rel="noreferrer noopener"
            aria-label={`${action.label} — opens in a new tab`}
          >
            {action.label}
            <Icon name="arrow-right" size={15} />
          </a>
        ) : (
          <a className="link-more" href={action.href}>
            {action.label}
            <Icon name="arrow-right" size={15} />
          </a>
        )
      ) : (
        <span className="muted tiny">Not configured yet.</span>
      )}
    </div>
  )
}

/** The public contact form. Field requirements come from the admin settings. */
function ContactForm({ settings }) {
  const toast = useToast()
  const [values, setValues] = useState(EMPTY_FORM)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [sent, setSent] = useState(false)

  const referenceEnabled = settings.form_booking_reference_enabled

  const update = (field) => (event) => {
    const { value } = event.target
    setValues((current) => ({ ...current, [field]: value }))
    setErrors((current) => (current[field] ? { ...current, [field]: undefined } : current))
  }

  const validate = () => {
    const next = {}
    const name = values.name.trim()
    if (settings.form_name_required && !name) {
      next.name = 'Please enter your name.'
    } else if (name && name.length < NAME_MIN) {
      next.name = `Name must be at least ${NAME_MIN} characters.`
    }

    const email = values.email.trim()
    if (settings.form_email_required && !email) {
      next.email = 'Please enter your email address.'
    } else if (email && !EMAIL_RE.test(email)) {
      next.email = 'Enter a valid email address, e.g. name@example.com.'
    }

    const phone = values.phone.trim()
    if (settings.form_phone_enabled) {
      if (settings.form_phone_required && !phone) {
        next.phone = 'Please enter your phone number.'
      } else if (phone && !MOBILE_RE.test(normaliseMobile(phone))) {
        next.phone = 'Enter a valid 10-digit mobile number.'
      }
    }

    if (settings.form_subject_required && !values.subject.trim()) {
      next.subject = 'Please add a subject.'
    }

    if (settings.form_message_required && !values.message.trim()) {
      next.message = 'Please tell us how we can help.'
    }

    const reference = values.booking_reference.trim()
    if (referenceEnabled && settings.form_booking_reference_required && !reference) {
      next.booking_reference = 'Please add your booking reference.'
    } else if (reference && !REFERENCE_RE.test(reference)) {
      next.booking_reference = 'Booking references look like SKY-7F3K9A.'
    }

    return next
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (submitting) return

    const found = validate()
    setErrors(found)
    // Move focus to the first problem so keyboard users are not stranded. Look it
    // up by id, because the aria-invalid attributes are only painted on the next
    // render — the DOM still looks valid at this point.
    const firstInvalid = FIELD_ORDER.find((field) => found[field])
    if (firstInvalid) {
      document.getElementById(`contact-${firstInvalid}`)?.focus()
      return
    }

    setSubmitting(true)
    try {
      await api.site.sendContactMessage({
        name: values.name.trim(),
        email: values.email.trim(),
        phone: settings.form_phone_enabled ? normaliseMobile(values.phone) : '',
        booking_reference: referenceEnabled ? values.booking_reference.trim() : '',
        subject: values.subject.trim(),
        message: values.message.trim(),
      })
      setValues(EMPTY_FORM)
      setSent(true)
      toast.success(settings.form_success_message)
    } catch (error) {
      const serverErrors = error.fieldErrors && typeof error.fieldErrors === 'object' ? error.fieldErrors : {}
      const mapped = {}
      Object.entries(serverErrors).forEach(([field, text]) => {
        const message = Array.isArray(text) ? text.join(' ') : String(text)
        if (!['detail', 'non_field_errors'].includes(field)) mapped[field] = message
      })
      setErrors(mapped)
      toast.error(settings.form_error_message || error.message)
    } finally {
      setSubmitting(false)
    }
  }

  const fieldProps = (field, required) => ({
    id: `contact-${field}`,
    name: field,
    value: values[field],
    onChange: update(field),
    className: `input ${errors[field] ? 'has-error' : ''}`.trim(),
    'aria-invalid': errors[field] ? 'true' : undefined,
    'aria-describedby': errors[field] ? `contact-${field}-error` : undefined,
    required,
  })

  return (
    <form className="contact-form card card--pad" onSubmit={handleSubmit} noValidate>
      <div className="contact-form__grid">
        <div className="field">
          <label className="field__label" htmlFor="contact-name">
            Full name{settings.form_name_required ? ' *' : ''}
          </label>
          <input {...fieldProps('name', settings.form_name_required)} type="text" autoComplete="name" placeholder="Jane Doe" />
          {errors.name ? (
            <span className="field__error" id="contact-name-error" role="alert">
              {errors.name}
            </span>
          ) : null}
        </div>

        <div className="field">
          <label className="field__label" htmlFor="contact-email">
            Email{settings.form_email_required ? ' *' : ''}
          </label>
          <input {...fieldProps('email', settings.form_email_required)} type="email" autoComplete="email" placeholder="you@example.com" />
          {errors.email ? (
            <span className="field__error" id="contact-email-error" role="alert">
              {errors.email}
            </span>
          ) : null}
        </div>

        {settings.form_phone_enabled ? (
          <div className="field">
            <label className="field__label" htmlFor="contact-phone">
              Phone{settings.form_phone_required ? ' *' : ' (optional)'}
            </label>
            <input
              {...fieldProps('phone', settings.form_phone_required)}
              type="tel"
              inputMode="numeric"
              autoComplete="tel-national"
              placeholder="10-digit mobile number"
            />
            {errors.phone ? (
              <span className="field__error" id="contact-phone-error" role="alert">
                {errors.phone}
              </span>
            ) : (
              <span className="field__hint">10-digit mobile number.</span>
            )}
          </div>
        ) : null}

        {referenceEnabled ? (
          <div className="field">
            <label className="field__label" htmlFor="contact-booking_reference">
              Booking reference{settings.form_booking_reference_required ? ' *' : ' (optional)'}
            </label>
            <input
              {...fieldProps('booking_reference', settings.form_booking_reference_required)}
              type="text"
              placeholder="SKY-7F3K9A"
            />
            <span className="field__hint">Found in your confirmation email.</span>
            {errors.booking_reference ? (
              <span className="field__error" id="contact-booking_reference-error" role="alert">
                {errors.booking_reference}
              </span>
            ) : null}
          </div>
        ) : null}

        <div className="field">
          <label className="field__label" htmlFor="contact-subject">
            Subject{settings.form_subject_required ? ' *' : ''}
          </label>
          <input {...fieldProps('subject', settings.form_subject_required)} type="text" placeholder="How can we help?" />
          {errors.subject ? (
            <span className="field__error" id="contact-subject-error" role="alert">
              {errors.subject}
            </span>
          ) : null}
        </div>

        <div className="field contact-form__message">
          <label className="field__label" htmlFor="contact-message">
            Message{settings.form_message_required ? ' *' : ''}
          </label>
          <textarea
            {...fieldProps('message', settings.form_message_required)}
            className={`textarea ${errors.message ? 'has-error' : ''}`.trim()}
            rows={5}
            placeholder="Tell us about your booking, dates or special requests…"
          />
          {errors.message ? (
            <span className="field__error" id="contact-message-error" role="alert">
              {errors.message}
            </span>
          ) : null}
        </div>
      </div>

      <div className="contact-form__actions">
        <button type="submit" className="btn btn--gold" disabled={submitting} aria-busy={submitting}>
          {submitting ? 'Sending…' : 'Send message'}
          {!submitting ? <Icon name="arrow-right" size={15} /> : null}
        </button>
        {sent ? (
          <p className="contact-form__sent" role="status">
            <Icon name="check-circle" size={16} />
            <span>{settings.form_success_message}</span>
          </p>
        ) : null}
      </div>
    </form>
  )
}

export default function Contact() {
  const { contact, loading } = useSite()
  const settings = contact?.settings
  const cards = contact?.cards || []
  const faqs = contact?.faqs || []

  // Page-level SEO from the CMS; the provider restores the site defaults when
  // the visitor navigates away.
  usePageMeta(
    settings ? { title: settings.seo_title, description: settings.seo_description } : null,
  )

  const location = settings?.location
  const mapUrl = location ? getMapUrl(location) : ''
  const directionsUrl = location ? getDirectionsUrl(location) : ''
  const embedUrl = location && location.has_coordinates ? getEmbedMapUrl(location) : ''

  const title = settings?.page_title || 'Contact us'
  const supportHours = settings?.support_hours || ''

  const primaryCta = useMemo(() => {
    if (!settings) return null
    return settings.primary_cta_text ? { text: settings.primary_cta_text, link: settings.primary_cta_link || '/hotels' } : null
  }, [settings])

  const secondaryCta = useMemo(() => {
    if (!settings) return null
    return settings.secondary_cta_text
      ? { text: settings.secondary_cta_text, link: settings.secondary_cta_link || '/contact' }
      : null
  }, [settings])

  return (
    <>
      <section className="page-hero">
        <div className="container">
          <nav className="breadcrumb" aria-label="Breadcrumb">
            <Link to="/">Home</Link>
            <span className="breadcrumb__sep" aria-hidden="true">/</span>
            <span aria-current="page">Contact</span>
          </nav>
          <h1>{title}</h1>
        </div>
      </section>

      <section className="section">
        <div className="container">
          {loading && !settings ? <Loader label="Loading contact details…" /> : null}

          {!loading && !settings ? (
            <div className="alert alert--error" role="alert">
              <Icon name="info" size={16} />
              <span>Contact details are unavailable right now. Please try again shortly.</span>
            </div>
          ) : null}

          {settings ? (
            <>
              {settings.intro_enabled && settings.intro_message ? (
                <div className="alert alert--info">
                  <Icon name="info" size={16} />
                  <span>{settings.intro_message}</span>
                </div>
              ) : null}

              {settings.cards_enabled && cards.length ? (
                <div className="contact-grid" style={{ marginTop: 'var(--space-6)' }}>
                  {cards.map((card, index) => (
                    <Reveal key={card.id} delay={index * 100}>
                      <ContactCard card={card} settings={{ ...settings, location }} />
                    </Reveal>
                  ))}
                </div>
              ) : null}

              {settings.response_time ? (
                <p className="contact-note">
                  <Icon name="clock" size={15} />
                  <span>{settings.response_time}</span>
                </p>
              ) : null}

              {primaryCta || secondaryCta ? (
                <div className="row-center wrap contact-actions">
                  {primaryCta ? (
                    <Link to={primaryCta.link} className="btn btn--gold">
                      {primaryCta.text}
                    </Link>
                  ) : null}
                  {secondaryCta ? (
                    <Link to={secondaryCta.link} className="btn btn--outline">
                      {secondaryCta.text}
                    </Link>
                  ) : null}
                </div>
              ) : null}

              {settings.booking_support_enabled && (settings.booking_support_title || settings.booking_support_button_text) ? (
                <Reveal>
                  <div className="support-band">
                    <div className="support-band__body">
                      <h2>{settings.booking_support_title}</h2>
                      {settings.booking_support_description ? (
                        <p className="muted">{settings.booking_support_description}</p>
                      ) : null}
                    </div>
                    {settings.booking_support_button_text ? (
                      <Link to={settings.booking_support_button_link || '/dashboard/bookings'} className="btn btn--gold">
                        {settings.booking_support_button_text}
                        <Icon name="arrow-right" size={15} />
                      </Link>
                    ) : null}
                  </div>
                </Reveal>
              ) : null}

              {settings.map_enabled ? (
                <section className="contact-block" aria-labelledby="contact-map-heading">
                  <div className="section-head">
                    <h2 id="contact-map-heading">Find us</h2>
                    {location?.full_address ? <p className="muted">{location.full_address}</p> : null}
                  </div>

                  {embedUrl ? (
                    <div className="map-embed">
                      <iframe
                        title={`Map showing ${location.property_name || 'our location'}`}
                        src={embedUrl}
                        loading="lazy"
                        referrerPolicy="no-referrer-when-downgrade"
                      />
                    </div>
                  ) : (
                    <div className="alert alert--warning">
                      <Icon name="map-pin" size={16} />
                      <span>The map location has not been published yet.</span>
                    </div>
                  )}

                  {(mapUrl || directionsUrl) && location?.has_coordinates ? (
                    <div className="row-center wrap contact-actions">
                      {directionsUrl ? (
                        <a className="btn btn--gold" href={directionsUrl} target="_blank" rel="noreferrer noopener">
                          Get directions
                          <Icon name="arrow-right" size={15} />
                        </a>
                      ) : null}
                      {mapUrl ? (
                        <a className="btn btn--outline" href={mapUrl} target="_blank" rel="noreferrer noopener">
                          View on map
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </section>
              ) : null}

              {settings.support_enabled && (settings.support_title || settings.support_description || supportHours) ? (
                <Reveal>
                  <section className="contact-block" aria-labelledby="contact-support-heading">
                    <div className="section-head">
                      <h2 id="contact-support-heading">{settings.support_title}</h2>
                    </div>
                    <div className="contact-card">
                      <span className="icon-tile" aria-hidden="true">
                        <Icon name="clock" size={20} />
                      </span>
                      {supportHours ? <p className="support-hours">{supportHours}</p> : null}
                      {settings.support_description ? (
                        <p className="muted tiny">{settings.support_description}</p>
                      ) : null}
                      {settings.email ? (
                        <a className="link-more" href={`mailto:${settings.email}`}>
                          {settings.email}
                          <Icon name="arrow-right" size={15} />
                        </a>
                      ) : null}
                    </div>
                  </section>
                </Reveal>
              ) : null}

              {settings.contact_form_enabled ? (
                <section className="contact-block" aria-labelledby="contact-form-heading">
                  <div className="section-head">
                    <h2 id="contact-form-heading">Send us a message</h2>
                    {settings.response_time ? <p className="muted">{settings.response_time}</p> : null}
                  </div>
                  <ContactForm settings={settings} />
                </section>
              ) : null}

              {settings.faq_enabled && faqs.length ? (
                <section className="contact-block" aria-labelledby="contact-faq-heading">
                  <div className="section-head">
                    <h2 id="contact-faq-heading">Frequently asked questions</h2>
                  </div>
                  <div className="faq-list">
                    {faqs.map((faq) => (
                      <details className="faq" key={faq.id}>
                        <summary>
                          <span>{faq.question}</span>
                          <Icon name="chevron-down" size={18} className="faq__chevron" />
                        </summary>
                        <p className="muted">{faq.answer}</p>
                      </details>
                    ))}
                  </div>
                </section>
              ) : null}
            </>
          ) : null}
        </div>
      </section>
    </>
  )
}
