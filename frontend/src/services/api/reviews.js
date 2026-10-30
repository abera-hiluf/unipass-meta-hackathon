import { api } from './client'

export const reviewCases = () => api.get('/identity/reviews')
export const reviewCase = (id, decision, reason) => api.post(`/identity/reviews/${id}`, { decision, reason })
