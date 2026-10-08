/**
 * Normalises a CMS gallery payload into `{ src, alt }` entries.
 *
 * The cover image is prepended when it is not already part of the gallery, so
 * every hotel/room shows at least one photo.
 */
export function resolveGallery(images = [], cover = null, alt = 'Photo') {
  const entries = (images || [])
    .map((image) => {
      const src = typeof image === 'string' ? image : image?.image
      if (!src) return null
      return { src, alt: image?.alt_text || image?.caption || alt }
    })
    .filter(Boolean)

  if (cover && !entries.some((entry) => entry.src === cover)) {
    entries.unshift({ src: cover, alt })
  }
  return entries
}

export default resolveGallery
