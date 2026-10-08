import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import AuthLayout from '../components/AuthLayout'
import Icon from '../components/Icon'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
// Mobile numbers are exactly 10 digits (country code is not stored).
const MOBILE_RE = /^\d{10}$/
const NAME_MIN = 3
// A single character is enough for a surname.
const LAST_NAME_MIN = 1
const USERNAME_MIN = 3

/** Strips spaces/dashes so a pasted number is accepted. */
function normaliseMobile(value) {
  const digits = String(value || '').replace(/\D/g, '')
  if (digits.length === 12 && digits.startsWith('91')) return digits.slice(2)
  if (digits.length === 11 && digits.startsWith('0')) return digits.slice(1)
  return digits
}

// Mirrors `accounts.serializers.password_strength_errors`.
const PASSWORD_RULES = [
  ['At least 8 characters', (value) => value.length >= 8],
  ['One uppercase letter', (value) => /[A-Z]/.test(value)],
  ['One lowercase letter', (value) => /[a-z]/.test(value)],
  ['One number', (value) => /\d/.test(value)],
  ['One special character', (value) => /[^A-Za-z0-9]/.test(value)],
]

/**
 * Client-side mirror of `RegisterSerializer` so mistakes are caught before a
 * round-trip. The backend stays the source of truth (uniqueness, strength).
 */
function validate(form) {
  const errors = {}
  const first = form.first_name.trim()
  const last = form.last_name.trim()
  const username = form.username.trim()
  const email = form.email.trim()

  if (!first) errors.first_name = 'First name is required.'
  else if (first.length < NAME_MIN) errors.first_name = `First name must be at least ${NAME_MIN} characters.`

  if (!last) errors.last_name = 'Last name is required.'
  else if (last.length < LAST_NAME_MIN) errors.last_name = `Last name must be at least ${LAST_NAME_MIN} character.`

  if (!username) errors.username = 'Username is required.'
  else if (username.length < USERNAME_MIN) {
    errors.username = `Username must be at least ${USERNAME_MIN} characters.`
  }

  if (!email) errors.email = 'Email is required.'
  else if (!EMAIL_RE.test(email)) errors.email = 'Enter a valid email address (e.g. name@example.com).'

  if (!form.phone.trim()) errors.phone = 'Phone number is required.'
  else if (!MOBILE_RE.test(normaliseMobile(form.phone))) {
    errors.phone = 'Enter a valid 10-digit mobile number.'
  }

  if (!form.city.trim()) errors.city = 'City is required.'
  if (!form.country.trim()) errors.country = 'Country is required.'
  if (!form.address.trim()) errors.address = 'Address is required.'

  if (!form.password) errors.password = 'Password is required.'
  else if (PASSWORD_RULES.some(([, test]) => !test(form.password))) {
    errors.password = 'Password does not meet all the requirements below.'
  }

  if (!form.password_confirm) errors.password_confirm = 'Please confirm your password.'
  else if (form.password !== form.password_confirm) errors.password_confirm = 'Passwords do not match.'

  return errors
}

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
    phone: '',
    city: '',
    country: '',
    address: '',
    password: '',
    password_confirm: '',
  })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState(null)
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)

  const update = (key) => (event) => {
    const { value } = event.target
    setForm((current) => ({ ...current, [key]: value }))
    setErrors((current) => ({ ...current, [key]: undefined }))
    setError(null)
  }

  const submit = async (event) => {
    event.preventDefault()

    const nextErrors = validate(form)
    setErrors(nextErrors)
    setError(null)

    const firstInvalid = Object.keys(nextErrors)[0]
    if (firstInvalid) {
      document.getElementById(`register-${firstInvalid}`)?.focus()
      return
    }

    setBusy(true)
    try {
      await register({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        username: form.username.trim(),
        email: form.email.trim(),
        phone: normaliseMobile(form.phone),
        city: form.city.trim(),
        country: form.country.trim(),
        address: form.address.trim(),
        password: form.password,
        password_confirm: form.password_confirm,
      })
      // The account exists but is not signed in yet — send them to the login
      // page (username prefilled) so they can confirm their password first.
      toast.success('Account created. Please sign in to continue.')
      navigate('/login', { replace: true, state: { registered: true, username: form.username.trim() } })
    } catch (requestError) {
      setError(requestError.message)
      setErrors(requestError.fieldErrors || {})
    } finally {
      setBusy(false)
    }
  }

  const fieldProps = (key, extra = {}) => ({
    id: `register-${key}`,
    className: `input ${errors[key] ? 'has-error' : ''}`.trim(),
    value: form[key],
    onChange: update(key),
    'aria-invalid': errors[key] ? true : undefined,
    'aria-describedby': errors[key] ? `register-${key}-error` : undefined,
    ...extra,
  })

  const FieldError = ({ name }) =>
    errors[name] ? (
      <span className="field__error" id={`register-${name}-error`}>
        {errors[name]}
      </span>
    ) : null

  return (
    <AuthLayout
      title="Create your account"
      subtitle="Book faster, track your stays and unlock member-only offers."
      asideTitle="Join thousands of happy travellers"
      asideText="Members get exclusive rates, free cancellation on selected rooms and instant booking history."
    >
      <form onSubmit={submit} noValidate>
        <div className="guest-grid">
          <label className="field">
            <span className="field__label">First name</span>
            <input {...fieldProps('first_name', { autoComplete: 'given-name', required: true, minLength: NAME_MIN })} />
            <FieldError name="first_name" />
          </label>
          <label className="field">
            <span className="field__label">Last name</span>
            <input {...fieldProps('last_name', { autoComplete: 'family-name', required: true, minLength: LAST_NAME_MIN })} />
            <FieldError name="last_name" />
          </label>
        </div>

        <label className="field">
          <span className="field__label">Username</span>
          <input
            {...fieldProps('username', {
              autoComplete: 'username',
              required: true,
              minLength: USERNAME_MIN,
            })}
          />
          {!errors.username ? (
            <span className="field__hint">At least {USERNAME_MIN} characters.</span>
          ) : null}
          <FieldError name="username" />
        </label>

        <div className="guest-grid">
          <label className="field">
            <span className="field__label">Email</span>
            <input {...fieldProps('email', { type: 'email', autoComplete: 'email', required: true })} />
            <FieldError name="email" />
          </label>
          <label className="field">
            <span className="field__label">Phone number</span>
            <input
              {...fieldProps('phone', {
                type: 'tel',
                inputMode: 'numeric',
                autoComplete: 'tel-national',
                required: true,
                placeholder: '10-digit mobile number',
              })}
            />
            {!errors.phone ? (
              <span className="field__hint">10-digit mobile number.</span>
            ) : null}
            <FieldError name="phone" />
          </label>
        </div>

        <div className="guest-grid">
          <label className="field">
            <span className="field__label">City</span>
            <input {...fieldProps('city', { autoComplete: 'address-level2', required: true, placeholder: 'Chennai' })} />
            <FieldError name="city" />
          </label>
          <label className="field">
            <span className="field__label">Country</span>
            <input {...fieldProps('country', { autoComplete: 'country-name', required: true, placeholder: 'India' })} />
            <FieldError name="country" />
          </label>
        </div>

        <label className="field">
          <span className="field__label">Address</span>
          <input
            {...fieldProps('address', {
              autoComplete: 'street-address',
              required: true,
              placeholder: 'Street, area, landmark',
            })}
          />
          <FieldError name="address" />
        </label>

        <div className="guest-grid">
          <label className="field">
            <span className="field__label">Password</span>
            <input
              {...fieldProps('password', {
                type: showPassword ? 'text' : 'password',
                autoComplete: 'new-password',
                required: true,
                minLength: 8,
              })}
            />
            <FieldError name="password" />
          </label>
          <label className="field">
            <span className="field__label">Confirm password</span>
            <input
              {...fieldProps('password_confirm', {
                type: showPassword ? 'text' : 'password',
                autoComplete: 'new-password',
                required: true,
              })}
            />
            <FieldError name="password_confirm" />
          </label>
        </div>

        <ul className="password-rules" aria-label="Password requirements">
          {PASSWORD_RULES.map(([label, test]) => {
            const met = test(form.password)
            return (
              <li key={label} className={met ? 'is-met' : ''}>
                <Icon name={met ? 'check' : 'close'} size={12} />
                {label}
              </li>
            )
          })}
        </ul>

        <label className="row-center" style={{ gap: 8, marginBottom: 'var(--space-4)' }}>
          <input
            type="checkbox"
            checked={showPassword}
            onChange={(event) => setShowPassword(event.target.checked)}
          />
          <span className="tiny muted">Show passwords</span>
        </label>

        {error ? (
          <div className="alert alert--error" style={{ marginBottom: 'var(--space-4)' }} role="alert">
            <Icon name="info" size={16} />
            <span>{error}</span>
          </div>
        ) : null}

        <button type="submit" className="btn btn--gold btn--block btn--lg" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
          <Icon name="arrow-right" size={16} />
        </button>
      </form>

      <p className="auth-card__foot">
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </AuthLayout>
  )
}
