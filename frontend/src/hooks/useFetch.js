import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Runs an async loader whenever `deps` change.
 *
 * The loader receives an AbortSignal so in-flight requests are cancelled when
 * the component unmounts or the deps change — no state updates after teardown.
 *
 *   const { data, loading, error, reload } = useFetch(
 *     (signal) => api.hotels.list({ city }, { signal }),
 *     [city],
 *   )
 */
export default function useFetch(loader, deps = [], { initialData = null } = {}) {
  const [state, setState] = useState({ data: initialData, loading: true, error: null })
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  const [nonce, setNonce] = useState(0)
  const reload = useCallback(() => setNonce((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    setState((previous) => ({ ...previous, loading: true, error: null }))

    Promise.resolve(loaderRef.current(controller.signal))
      .then((data) => {
        if (active) setState({ data, loading: false, error: null })
      })
      .catch((error) => {
        if (!active || error.name === 'AbortError') return
        setState({ data: initialData, loading: false, error })
      })

    return () => {
      active = false
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  return { ...state, reload, setData: (data) => setState((prev) => ({ ...prev, data })) }
}
