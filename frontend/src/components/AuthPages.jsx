import React, { useState } from 'react'
import { Lock, Mail, User as UserIcon, ShieldAlert, ArrowRight, KeyRound } from 'lucide-react'
import { setAccessToken } from '../utils/authClient'

export function CandidateAuthPage({ mode = 'login', onNavigate, onAuthSuccess }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [resetToken, setResetToken] = useState(() => {
    if (typeof window === 'undefined') return ''
    return new URLSearchParams(window.location.search).get('token') || ''
  })
  const [newPassword, setNewPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      if (mode === 'login') {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Sign in failed.')
        setAccessToken(data.access_token)
        onAuthSuccess(data.user)
        return
      }
      if (mode === 'register') {
        const res = await fetch('/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ email, password, full_name: fullName }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Registration failed.')
        setAccessToken(data.access_token)
        onAuthSuccess(data.user)
        return
      }
      if (mode === 'forgot-password') {
        const res = await fetch('/api/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Unable to process request.')
        setNotice(data.message)
        return
      }
      if (mode === 'reset-password') {
        const res = await fetch('/api/auth/reset-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: resetToken, new_password: newPassword }),
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Password reset failed.')
        setNotice('Password updated cleanly. You may now sign in with your new credentials.')
      }
    } catch (err) {
      setError(err.message || 'Authentication error.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-md mx-auto py-10 px-4">
      <div className="bg-white border-[3px] border-black rounded-3xl p-7 shadow-[8px_8px_0px_0px_#000] space-y-6">
        <div className="space-y-1 border-b-2 border-black pb-4">
          <span className="inline-block px-2.5 py-0.5 rounded bg-[#67E8F9] border border-black text-[10px] font-black uppercase">
            Candidate Portal
          </span>
          <h1 className="text-2xl font-black uppercase text-black tracking-tight">
            {mode === 'login' && 'Candidate Sign In'}
            {mode === 'register' && 'Create Candidate Account'}
            {mode === 'forgot-password' && 'Recover Account Access'}
            {mode === 'reset-password' && 'Set New Password'}
          </h1>
          <p className="text-xs font-bold text-slate-600">
            Access persistent profiles, resume review, tailored job matches, and verified reports.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onNavigate('/login')}
            className={`px-3 py-1 rounded-lg border-2 border-black text-xs font-black uppercase ${
              mode === 'login' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => onNavigate('/register')}
            className={`px-3 py-1 rounded-lg border-2 border-black text-xs font-black uppercase ${
              mode === 'register' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            Register
          </button>
          <button
            type="button"
            onClick={() => onNavigate('/forgot-password')}
            className={`px-3 py-1 rounded-lg border-2 border-black text-xs font-black uppercase ${
              mode === 'forgot-password' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            Forgot Password
          </button>
        </div>

        {error && (
          <div className="p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold text-black">
            {error}
          </div>
        )}
        {notice && (
          <div className="p-3 bg-[#DCFCE7] border-2 border-black rounded-xl text-xs font-bold text-black">
            {notice}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === 'register' && (
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase flex items-center space-x-1">
                <UserIcon className="w-3.5 h-3.5" />
                <span>Full Name</span>
              </span>
              <input
                type="text"
                required
                minLength={2}
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Jane Doe"
                className="w-full px-3 py-2.5 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
          )}

          {(mode === 'login' || mode === 'register' || mode === 'forgot-password') && (
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase flex items-center space-x-1">
                <Mail className="w-3.5 h-3.5" />
                <span>Email</span>
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3 py-2.5 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
          )}

          {(mode === 'login' || mode === 'register') && (
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase flex items-center space-x-1">
                <Lock className="w-3.5 h-3.5" />
                <span>Password</span>
              </span>
              <input
                type="password"
                required
                minLength={mode === 'register' ? 10 : 1}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={mode === 'register' ? '10+ chars with letters & digits/symbols' : 'Enter password'}
                className="w-full px-3 py-2.5 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
          )}

          {mode === 'reset-password' && (
            <>
              <label className="block space-y-1">
                <span className="text-xs font-black uppercase flex items-center space-x-1">
                  <KeyRound className="w-3.5 h-3.5" />
                  <span>Reset Token</span>
                </span>
                <input
                  type="text"
                  required
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border-2 border-black bg-[#F4F0EA] font-mono text-xs"
                />
              </label>
              <label className="block space-y-1">
                <span className="text-xs font-black uppercase">New Password</span>
                <input
                  type="password"
                  required
                  minLength={10}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
                />
              </label>
            </>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full py-3 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] flex items-center justify-center space-x-2 disabled:opacity-60"
          >
            <span>{busy ? 'Submitting...' : 'Continue'}</span>
            <ArrowRight className="w-4 h-4 stroke-[2.5]" />
          </button>
        </form>

        <div className="pt-3 border-t-2 border-black flex items-center justify-between text-[11px] font-bold text-slate-600">
          <button type="button" onClick={() => onNavigate('/reset-password')} className="underline hover:text-black">
            Have a reset token?
          </button>
          <button type="button" onClick={() => onNavigate('/admin/login')} className="underline hover:text-black">
            Administrator Sign In →
          </button>
        </div>
      </div>
    </div>
  )
}

export function AdminLoginPage({ onNavigate, onAuthSuccess }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const res = await fetch('/api/auth/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Administrator authentication failed.')
      setAccessToken(data.access_token)
      onAuthSuccess(data.user)
    } catch (err) {
      setError(err.message || 'Administrator sign in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="max-w-md mx-auto py-10 px-4">
      <div className="bg-white border-[3px] border-black rounded-3xl p-7 shadow-[8px_8px_0px_0px_#000] space-y-6">
        <div className="space-y-1 border-b-2 border-black pb-4">
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded bg-[#FECDD3] border border-black text-[10px] font-black uppercase">
            <ShieldAlert className="w-3 h-3" />
            <span>Restricted Admin Console</span>
          </span>
          <h1 className="text-2xl font-black uppercase text-black tracking-tight">Administrator Sign In</h1>
          <p className="text-xs font-bold text-slate-600">
            Separate privilege portal for legacy session attribution, RBAC governance, and audit oversight.
          </p>
        </div>

        {error && (
          <div className="p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold text-black">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block space-y-1">
            <span className="text-xs font-black uppercase">Admin Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@company.com"
              className="w-full px-3 py-2.5 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
            />
          </label>
          <label className="block space-y-1">
            <span className="text-xs font-black uppercase">Password</span>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="w-full py-3 rounded-xl bg-black hover:bg-slate-800 border-2 border-black font-black text-white text-xs uppercase shadow-[4px_4px_0px_0px_#FFE600] disabled:opacity-60"
          >
            {busy ? 'Verifying Admin Session...' : 'Enter Admin Console'}
          </button>
        </form>

        <div className="pt-3 border-t-2 border-black text-right text-[11px] font-bold">
          <button type="button" onClick={() => onNavigate('/login')} className="underline text-slate-600 hover:text-black">
            ← Back to Candidate Portal
          </button>
        </div>
      </div>
    </div>
  )
}

