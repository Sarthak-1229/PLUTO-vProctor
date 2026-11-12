import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { readCookie, resolveRouteAccess } from '../src/utils/authClient.js'

describe('Frontend auth & RBAC route guards', () => {
  it('blocks unauthenticated users from candidate and admin routes when authEnabled is true', () => {
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/', authEnabled: true, user: null }),
      { allowed: false, redirectTo: '/login', view: 'login' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/profile', authEnabled: false, user: null }),
      { allowed: false, redirectTo: '/login', view: 'login' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/admin', authEnabled: true, user: null }),
      { allowed: false, redirectTo: '/admin/login', view: 'admin-login' },
    )
  })

  it('prevents candidates from entering admin routes', () => {
    const candidate = { id: 'usr_1', role: 'candidate' }
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/admin', authEnabled: true, user: candidate }),
      { allowed: false, redirectTo: '/', view: 'practice' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/admin/login', authEnabled: true, user: candidate }),
      { allowed: false, redirectTo: '/', view: 'practice' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/recommendations', authEnabled: true, user: candidate }),
      { allowed: true, redirectTo: null, view: 'recommendations' },
    )
  })

  it('routes administrators cleanly into admin console and allows offline practice when authEnabled is false', () => {
    const admin = { id: 'usr_a', role: 'admin' }
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/admin', authEnabled: true, user: admin }),
      { allowed: true, redirectTo: null, view: 'admin' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/admin/login', authEnabled: true, user: admin }),
      { allowed: false, redirectTo: '/admin', view: 'admin' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/', authEnabled: false, user: null }),
      { allowed: true, redirectTo: null, view: 'practice' },
    )
  })

  it('parses CSRF cookie values safely', () => {
    const raw = 'other=123; pluto_csrf_token=abc%2Bdef_123; theme=light'
    assert.equal(readCookie('pluto_csrf_token', raw), 'abc+def_123')
    assert.equal(readCookie('missing', raw), null)
  })
})

