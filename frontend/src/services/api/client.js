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
  if (!error?.response) return 'The API is unavailable. Check that the backend is running.'
  return error.response.data?.detail || 'The request could not be completed.'
}
