import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('unipass_access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      sessionStorage.removeItem('unipass_access_token')
      window.dispatchEvent(new Event('unipass:unauthorized'))
    }
    return Promise.reject(error)
  },
)

export function apiMessage(error) {
  if (!error?.response) {
    if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') {
      return 'The API request timed out. Check the backend connection and try again.'
    }
    return `Could not connect to the API at ${API_BASE_URL}. Check the URL, backend availability, and CORS configuration.`
  }

  const { status, data } = error.response
  const detail = data?.detail
  if (status === 422 && Array.isArray(detail)) {
    return detail.map((item) => {
      const field = Array.isArray(item.loc) ? item.loc.slice(1).join('.') : ''
      return field ? `${field}: ${item.msg}` : item.msg
    }).join(' ')
  }
  if (typeof detail === 'string') return detail
  if (status === 401) return 'Authentication failed. Check your credentials and try again.'
  if (status === 403) return 'You are not authorized to perform this action.'
  if (status >= 500) return `The server encountered an error (HTTP ${status}). Please try again later.`
  return `The request could not be completed (HTTP ${status}).`
}
