import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'

const SiteContext = createContext(null)

/**
 * Loads the branding payload once (site title, logo, contact details, nav links)
 * so the header, footer and document head are all driven by the Django CMS.
 *
 * The Contact CMS payload rides along with it: the Contact page, its cards and
 * the footer all read the same contact data, so they always agree.
 */
export function SiteProvider({ children }) {
  const [settings, setSettings] = useState(null)
  const [contact, setContact] = useState(null)
  const [pageMeta, setPageMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async (signal) => {
    setLoading(true)
    try {
      const [data, contactData] = await Promise.all([
        api.site.settings({ signal }),
        // A missing contact record must never take the whole site down.
        api.site.contact({ signal }).catch(() => null),
      ])
      setSettings(data)
      setContact(contactData)
      setError(null)
      return data
    } catch (requestError) {
      if (requestError.name !== 'AbortError') setError(requestError)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  // Keep the browser tab and favicon in sync with the CMS. A page that calls
  // `usePageMeta` (the Contact page's SEO fields) wins over the site defaults;
  // depending on `pageMeta` means this always runs *after* the page sets it.
  useEffect(() => {
    if (!settings) return
    document.title =
      pageMeta?.title ||
      (settings.tagline ? `${settings.site_title} — ${settings.tagline}` : settings.site_title)

    const description = pageMeta?.description || settings.meta_description
    if (description) {
      let meta = document.querySelector('meta[name="description"]')
      if (!meta) {
        meta = document.createElement('meta')
        meta.name = 'description'
        document.head.appendChild(meta)
      }
      meta.content = description
    }

    if (settings.favicon_display) {
      // The app ships a static favicon set in index.html; when the admin uploads
      // one it must win outright, so drop the defaults rather than leaving
      // several competing <link rel="icon"> tags for the browser to pick from.
      document
        .querySelectorAll('link[rel="icon"], link[rel="shortcut icon"], link[rel="apple-touch-icon"]')
        .forEach((element) => element.remove())

      const link = document.createElement('link')
      link.rel = 'icon'
      link.href = settings.favicon_display
      document.head.appendChild(link)
    }
  }, [settings, pageMeta])

  const value = useMemo(
    () => ({
      settings,
      contact,
      contactSettings: contact?.settings || null,
      contactLocation: contact?.settings?.location || null,
      setPageMeta,
      loading,
      error,
      reload: load,
      currency: settings?.currency_symbol || '₹',
      title: settings?.site_title || 'SkyStay',
    }),
    [settings, contact, loading, error, load],
  )

  return <SiteContext.Provider value={value}>{children}</SiteContext.Provider>
}

export function useSite() {
  const context = useContext(SiteContext)
  if (!context) throw new Error('useSite must be used inside a SiteProvider')
  return context
}

/**
 * Override the document title/description for the current page.
 *
 *   usePageMeta({ title: settings.seo_title, description: settings.seo_description })
 *
 * Cleared automatically on unmount so the next page falls back to the site
 * defaults. The payload is serialised so an inline object literal does not
 * retrigger the effect on every render.
 */
export function usePageMeta(meta) {
  const { setPageMeta } = useSite()
  const serialised = JSON.stringify(meta || null)

  useEffect(() => {
    setPageMeta(JSON.parse(serialised))
    return () => setPageMeta(null)
  }, [serialised, setPageMeta])
}

export default SiteContext
