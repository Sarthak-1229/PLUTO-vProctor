/**
 * Frontend authentication client, CSRF cookie reader, silent refresh queue, and SPA route guards.
 */

let _accessToken = null
let _refreshPromise = null

export function setAccessToken(token) {
  _accessToken = token || null
}

export function getAccessToken() {
  return _accessToken
}

export function readCookie(name, cookieSource = typeof document !== 'undefined' ? document.cookie : '') {
  if (!cookieSource) return null
  const prefix = `${name}=`
  const parts = cookieSource.split(';')
  for (const part of parts) {
    const trimmed = part.trim()
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length))
    }
  }
  return null
}

export async function refreshAccessToken() {
  if (_refreshPromise) return _refreshPromise

  _refreshPromise = (async () => {
    try {
      const csrf = readCookie('pluto_csrf_token')
      const headers = {}
      if (csrf) {
        headers['X-CSRF-Token'] = csrf
      }
      const res = await fetch('/api/auth/refresh', {
        method: 'POST',
        credentials: 'include',
        headers,
      })
      if (!res.ok) {
        setAccessToken(null)
        return null
      }
      const data = await res.json()
      setAccessToken(data.access_token || null)
      return data
    } catch {
      setAccessToken(null)
      return null
    } finally {
      _refreshPromise = null
    }
  })()

  return _refreshPromise
}

export async function authFetch(url, options = {}) {
  const headers = new Headers(options.headers || {})
  if (_accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${_accessToken}`)
  }

  let res = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  })

  if (res.status === 401 && !String(url).startsWith('/api/auth/')) {
    const refreshed = await refreshAccessToken()
    if (refreshed && refreshed.access_token) {
      const retryHeaders = new Headers(options.headers || {})
      retryHeaders.set('Authorization', `Bearer ${refreshed.access_token}`)
      res = await fetch(url, {
        ...options,
        headers: retryHeaders,
        credentials: 'include',
      })
    }
  }

  return res
}

/**
 * Pure SPA route guard returning { allowed, redirectTo, view }.
 */
export function resolveRouteAccess({ pathname, authEnabled, user }) {
  const cleanPath = (pathname || '/').replace(/\/+$/, '') || '/'
  const role = user?.role || null
  const isAdmin = role === 'admin' || role === 'super_admin'

  if (cleanPath.startsWith('/dev/record-fixture')) {
    return { allowed: true, redirectTo: null, view: 'record-fixture' }
  }

  if (cleanPath === '/admin/login') {
    if (isAdmin) return { allowed: false, redirectTo: '/admin', view: 'admin' }
    if (user) return { allowed: false, redirectTo: '/', view: 'practice' }
    return { allowed: true, redirectTo: null, view: 'admin-login' }
  }

  if (cleanPath === '/admin' || cleanPath.startsWith('/admin/')) {
    if (!user) return { allowed: false, redirectTo: '/admin/login', view: 'admin-login' }
    if (!isAdmin) return { allowed: false, redirectTo: '/', view: 'practice' }
    return { allowed: true, redirectTo: null, view: 'admin' }
  }

  if (cleanPath === '/login' || cleanPath === '/register' || cleanPath === '/forgot-password' || cleanPath === '/reset-password') {
    if (isAdmin) return { allowed: false, redirectTo: '/admin', view: 'admin' }
    if (user) return { allowed: false, redirectTo: '/', view: 'practice' }
    return { allowed: true, redirectTo: null, view: cleanPath.slice(1) }
  }

  if (cleanPath === '/profile' || cleanPath === '/resumes' || cleanPath === '/recommendations' || cleanPath === '/roadmap') {
    if (!user) return { allowed: false, redirectTo: '/login', view: 'login' }
    return { allowed: true, redirectTo: null, view: cleanPath.slice(1) }
  }

  if (cleanPath === '/rooms/join') {
    if (authEnabled && !user) return { allowed: false, redirectTo: '/login', view: 'login' }
    return { allowed: true, redirectTo: null, view: 'rooms-join' }
  }

  if (cleanPath.startsWith('/rooms/')) {
    if (authEnabled && !user) return { allowed: false, redirectTo: '/login', view: 'login' }
    return { allowed: true, redirectTo: null, view: 'live-room' }
  }

  if (cleanPath === '/report') {
    return { allowed: true, redirectTo: '/', view: 'practice' }
  }

  if (cleanPath.startsWith('/report/')) {
    const sessionId = cleanPath.slice('/report/'.length).trim()
    if (!sessionId) {
      return { allowed: true, redirectTo: '/', view: 'practice' }
    }
    if (authEnabled && !user) {
      return { allowed: false, redirectTo: '/login', view: 'login' }
    }
    return { allowed: true, redirectTo: null, view: 'report', sessionId }
  }

  if (authEnabled && !user) {
    return { allowed: false, redirectTo: '/login', view: 'login' }
  }

  return { allowed: true, redirectTo: null, view: 'practice' }
}

