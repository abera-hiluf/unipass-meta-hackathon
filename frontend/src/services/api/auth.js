import { api } from './client'

export const register = (payload) => api.post('/auth/register', payload)
export const login = (payload) => api.post('/auth/login', payload)
export const me = () => api.get('/auth/me')
