import { api } from './client'

export const identityStatus = () => api.get('/identity/status')
export const uploadDocument = (documentType, file) => {
  const form = new FormData()
  form.append('document_type', documentType)
  form.append('file', file)
  return api.post('/identity/documents', form)
}
export const documentStatus = (id) => api.get(`/identity/documents/${id}`)
export const analyzeDocument = (id) => api.post(`/identity/documents/${id}/analyze`)
export const submitSelfie = (id, file) => {
  const form = new FormData()
  form.append('consent', 'true')
  form.append('capture_state', 'captured')
  form.append('file', file)
  return api.post(`/identity/verifications/${id}/selfie`, form)
}
export const issueLivenessChallenge = (id) => api.post(`/identity/verifications/${id}/liveness/challenge`)
export const submitLiveness = (id, challengeId, file) => {
  const form = new FormData()
  form.append('challenge_id', challengeId)
  form.append('consent', 'true')
  form.append('capture_state', 'completed_challenge')
  form.append('file', file)
  return api.post(`/identity/verifications/${id}/liveness`, form)
}
export const livenessStatus = (id) => api.get(`/identity/verifications/${id}/liveness`)
export const runFaceMatch = (id) => api.post(`/identity/verifications/${id}/face-match`)
export const faceMatchStatus = (id) => api.get(`/identity/verifications/${id}/face-match`)
