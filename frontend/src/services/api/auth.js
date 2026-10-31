import { api } from './client'

export const register = (payload) => api.post('/auth/register', payload)
export const login = (payload) => api.post('/auth/login', payload)
export const me = () => api.get('/auth/me')
export const emailOwnershipStatus = () => api.get('/auth/email-verification')
export const sendEmailOwnershipCode = (email) => api.post('/auth/email-verification/code', { email })
export const confirmEmailOwnershipCode = (code) => api.post('/auth/email-verification/confirm', { code })
