import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api, tokenStore } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(tokenStore.get()))

  // Restore the session from the stored token on first paint.
  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false)
      return undefined
    }

    const controller = new AbortController()
    let active = true

    api.auth
      .me({ signal: controller.signal })
      .then((profile) => {
        if (active) setUser(profile)
      })
      .catch((error) => {
        // An aborted request (StrictMode remount, navigation) must NOT sign the
        // user out — only a genuine rejection means the token is no longer valid.
        if (!active || error.name === 'AbortError') return
        tokenStore.clear()
        setUser(null)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [])

  const login = useCallback(async (username, password) => {
    const payload = await api.auth.login({ username, password })
    tokenStore.set(payload.token)
    setUser(payload.user)
    return payload.user
  }, [])

  // Registration is intentionally non-authenticating: the account is created
  // but no token is stored, so the visitor stays signed out until they log in.
  const register = useCallback(async (form) => {
    const payload = await api.auth.register(form)
    return payload.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.auth.logout()
    } catch {
      // The token may already be gone server side — sign out locally regardless.
    }
    tokenStore.clear()
    setUser(null)
  }, [])

  const updateProfile = useCallback(async (form) => {
    const updated = await api.auth.updateMe(form)
    setUser(updated)
    return updated
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      updateProfile,
    }),
    [user, loading, login, register, logout, updateProfile],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside an AuthProvider')
  return context
}

export default AuthContext
