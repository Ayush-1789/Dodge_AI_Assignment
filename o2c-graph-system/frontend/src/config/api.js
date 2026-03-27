const rawBase = (import.meta.env.VITE_API_BASE_URL || '').trim()

// If VITE_API_BASE_URL is not set, use same-origin for local dev via Vite proxy.
const API_BASE_URL = rawBase.replace(/\/$/, '')

export function buildApiUrl(path) {
  const normalizedPath = String(path || '').startsWith('/') ? path : `/${path}`
  return `${API_BASE_URL}${normalizedPath}`
}

export { API_BASE_URL }
