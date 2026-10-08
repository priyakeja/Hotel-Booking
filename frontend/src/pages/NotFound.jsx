import { Link } from 'react-router-dom'

import Icon from '../components/Icon'

export default function NotFound() {
  return (
    <div className="container">
      <div className="error-page">
        <span className="error-page__code">404</span>
        <h1>This page has checked out</h1>
        <p className="muted" style={{ maxWidth: '46ch' }}>
          The page you were looking for doesn&apos;t exist or has moved. Let&apos;s get you back to somewhere
          comfortable.
        </p>
        <div className="row-center wrap" style={{ gap: 'var(--space-3)' }}>
          <Link to="/" className="btn btn--gold">
            <Icon name="arrow-left" size={16} />
            Back to home
          </Link>
          <Link to="/hotels" className="btn btn--outline">
            Browse hotels
          </Link>
        </div>
      </div>
    </div>
  )
}
