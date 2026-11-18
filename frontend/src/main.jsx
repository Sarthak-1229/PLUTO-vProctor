import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

// In hosted Catalyst builds, route relative /api/*, /health, and /ready fetches
// to the deployed AppSail backend origin configured via VITE_API_BASE_URL.
const apiBase = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '')
if (apiBase && typeof window !== 'undefined' && typeof window.fetch === 'function') {
  const originalFetch = window.fetch.bind(window)
  window.fetch = (input, init) => {
    if (typeof input === 'string' && (input.startsWith('/api/') || input === '/health' || input === '/ready')) {
      return originalFetch(`${apiBase}${input}`, init)
    }
    return originalFetch(input, init)
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
