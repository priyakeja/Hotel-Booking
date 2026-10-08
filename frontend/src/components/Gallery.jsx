import { useState } from 'react'

import { resolveGallery } from '../utils/images'
import Icon from './Icon'
import Modal from './Modal'

/**
 * Gallery layout: one large hero image plus two thumbnails, opening a lightbox
 * that steps through every CMS-uploaded image.
 */
export default function Gallery({ images = [], title = 'Gallery', cover = null, badge = null }) {
  const gallery = resolveGallery(images, cover, title)
  const [open, setOpen] = useState(false)
  const [index, setIndex] = useState(0)

  if (!gallery.length) {
    return <div className="gallery__main skeleton" style={{ borderRadius: 'var(--radius-lg)' }} />
  }

  const openAt = (position) => {
    setIndex(position)
    setOpen(true)
  }

  const step = (delta) => {
    setIndex((current) => (current + delta + gallery.length) % gallery.length)
  }

  return (
    <>
      <div className="gallery">
        <button type="button" className="gallery__main" onClick={() => openAt(0)} aria-label="Open photo gallery">
          <img src={gallery[0].src} alt={gallery[0].alt} />
          {badge}
        </button>

        {gallery.length > 1 ? (
          <div className="gallery__side">
            {gallery.slice(1, 3).map((image, position) => (
              <button
                key={image.src + position}
                type="button"
                className="gallery__thumb"
                onClick={() => openAt(position + 1)}
                aria-label={`Open photo ${position + 2}`}
              >
                <img src={image.src} alt={image.alt} loading="lazy" />
                {gallery.length > 3 && position === 1 ? (
                  <span className="gallery__more">+{gallery.length - 3} more</span>
                ) : null}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={`${title} photos`}
        maxWidth="760px"
        lockScroll={false}
      >
        <img className="gallery-modal__img" src={gallery[index]?.src} alt={gallery[index]?.alt} />

        <div className="row-between" style={{ marginBottom: 'var(--space-3)' }}>
          <button type="button" className="btn btn--outline btn--sm" onClick={() => step(-1)}>
            <Icon name="chevron-left" size={15} />
            Prev
          </button>
          <span className="tiny muted">
            {index + 1} / {gallery.length}
          </span>
          <button type="button" className="btn btn--outline btn--sm" onClick={() => step(1)}>
            Next
            <Icon name="chevron-right" size={15} />
          </button>
        </div>

        <div className="gallery-modal__thumbs">
          {gallery.map((image, position) => (
            <button
              key={`thumb-${image.src}-${position}`}
              type="button"
              className={`gallery-modal__thumb ${position === index ? 'is-active' : ''}`.trim()}
              onClick={() => setIndex(position)}
              aria-label={`Show photo ${position + 1}`}
            >
              <img src={image.src} alt="" loading="lazy" />
            </button>
          ))}
        </div>
      </Modal>
    </>
  )
}
