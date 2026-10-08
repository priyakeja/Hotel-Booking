import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import AuthLayout from '../components/AuthLayout'
import Icon from '../components/Icon'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const toast = useToast()

  const [form, setForm] = useState({ username: location.state?.username || '', password: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const redirectTo = location.state?.from || '/dashboard'
  // Set by the register page: the account was just created and needs a sign-in.
  const justRegistered = Boolean(location.state?.registered)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const user = await login(form.username.trim(), form.password)
      toast.success(`Welcome back, ${user.first_name || user.username}!`)
      navigate(redirectTo, { replace: true })
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title="Sign in to your account" subtitle="Access your bookings, reviews and saved hotels."    >
      {justRegistered ? (
        <div className="alert alert--success" style={{ marginBottom: 'var(--space-4)' }} role="status">
          <Icon name="check" size={16} />
          <span>Account created. Please sign in to continue.</span>
        </div>
      ) : null}

      <form onSubmit={submit} noValidate>
        <label className="field">
          <span className="field__label">Username or email</span>
          <input
            className="input"
            autoComplete="username"
            required
            value={form.username}
            onChange={(event) => setForm((c) => ({ ...c, username: event.target.value }))}
          />
        </label>

        <label className="field">
          <span className="field__label">Password</span>
          <input
            type="password"
            className="input"
            autoComplete="current-password"
            required
            value={form.password}
            onChange={(event) => setForm((c) => ({ ...c, password: event.target.value }))}
          />
        </label>

        {error ? (
          <div className="alert alert--error" style={{ marginBottom: 'var(--space-4)' }}>
            <Icon name="info" size={16} />
            <span>{error}</span>
          </div>
        ) : null}

        <button type="submit" className="btn btn--gold btn--block btn--lg" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
          <Icon name="arrow-right" size={16} />
        </button>
      </form>

      <div className="auth-demo">
        Demo accounts from the seeder:
        <br />
        Customer — <code>delyanka</code> / <code>demo12345</code>
        <br />
        Admin — <code>admin</code> / <code>admin12345</code>
      </div>

      <p className="auth-card__foot">
        New to us? <Link to="/register">Create an account</Link>
      </p>
    </AuthLayout>
  )
}
