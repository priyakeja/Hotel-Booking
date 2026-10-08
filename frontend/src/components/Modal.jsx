import { useEffect } from 'react'

import Icon from './Icon'

/**
 * Modal dialog: closes on Escape or backdrop click.
 *
 * `lockScroll` (default true) freezes the page behind the dialog. Pass
 * `lockScroll={false}` for viewers such as the photo lightbox, where the visitor
 * should still be able to scroll the page while the overlay is open.
 */
export default function Modal({
  open,
  onClose,
  title,
  children,
  maxWidth,
  labelledBy,
  lockScroll = true,
}) {
  useEffect(() => {
    if (!open) return undefined

    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose?.()
    }
    document.addEventListener('keydown', onKeyDown)

    const previousOverflow = document.body.style.overflow
    if (lockScroll) document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      if (lockScroll) document.body.style.overflow = previousOverflow
    }
  }, [open, onClose, lockScroll])

  if (!open) return null

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose?.()}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? labelledBy || 'modal-title' : undefined}
        style={maxWidth ? { maxWidth } : undefined}
      >
        <div className="modal__head">
          {title ? (
            <h3 className="modal__title" id={labelledBy || 'modal-title'}>
              {title}
            </h3>
          ) : (
            <span />
          )}
          <button type="button" className="modal__close" onClick={onClose} aria-label="Close dialog">
            <Icon name="close" size={17} />
          </button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>
  )
}
