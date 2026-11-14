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

  it('protects hosted interview room routes according to authentication status', () => {
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/rooms/join', authEnabled: true, user: null }),
      { allowed: false, redirectTo: '/login', view: 'login' },
    )
    const candidate = { id: 'usr_cand', role: 'candidate' }
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/rooms/join', authEnabled: true, user: candidate }),
      { allowed: true, redirectTo: null, view: 'rooms-join' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/rooms/room_12345', authEnabled: true, user: candidate }),
      { allowed: true, redirectTo: null, view: 'live-room' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/roadmap', authEnabled: true, user: null }),
      { allowed: false, redirectTo: '/login', view: 'login' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/roadmap', authEnabled: true, user: candidate }),
      { allowed: true, redirectTo: null, view: 'roadmap' },
    )
  })

  it('resolves report deep-linking routes for candidates, admins, and offline mode', () => {
    const candidate = { id: 'usr_cand', role: 'candidate' }
    const admin = { id: 'usr_admin', role: 'admin' }

    // 1. Unauthenticated access blocked when authEnabled is true
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/report/sess_abc123', authEnabled: true, user: null }),
      { allowed: false, redirectTo: '/login', view: 'login' },
    )

    // 2. Candidate access allowed with extracted sessionId
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/report/sess_abc123', authEnabled: true, user: candidate }),
      { allowed: true, redirectTo: null, view: 'report', sessionId: 'sess_abc123' },
    )

    // 3. Admin access allowed with extracted sessionId
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/report/sess_abc123', authEnabled: true, user: admin }),
      { allowed: true, redirectTo: null, view: 'report', sessionId: 'sess_abc123' },
    )

    // 4. Offline mode allows report access anonymously
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/report/sess_abc123', authEnabled: false, user: null }),
      { allowed: true, redirectTo: null, view: 'report', sessionId: 'sess_abc123' },
    )

    // 5. Handles trailing slash and complex session ID formatting
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/report/sess_8f29-c1b3_021a/', authEnabled: true, user: candidate }),
      { allowed: true, redirectTo: null, view: 'report', sessionId: 'sess_8f29-c1b3_021a' },
    )

    // 6. Bare /report without ID safely redirects to home
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/report', authEnabled: false, user: null }),
      { allowed: true, redirectTo: '/', view: 'practice' },
    )
    assert.deepEqual(
      resolveRouteAccess({ pathname: '/report/', authEnabled: false, user: null }),
      { allowed: true, redirectTo: '/', view: 'practice' },
    )
  })
})

