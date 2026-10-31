import { api } from './client'

export const identityStatus = () => api.get('/identity/status')
export const uploadDocument = (documentType, file, demoConfirmationComplete, onUploadProgress) => {
  const form = new FormData()
  form.append('document_type', documentType)
  form.append('file', file)
  if (demoConfirmationComplete) form.append('demo_confirmation_complete', 'true')
  return api.post('/identity/documents', form, { onUploadProgress, timeout: 60000 })
}
export const documentStatus = (id) => api.get(`/identity/documents/${id}`)
export const analyzeDocument = (id) => api.post(`/identity/documents/${id}/analyze`)
export const assessFaceMatch = (id) => api.post(`/identity/verifications/${id}/face-match`)
export const faceMatchStatus = (id) => api.get(`/identity/verifications/${id}/face-match`)
export const submitSelfie = (id, file, onUploadProgress) => {
  const form = new FormData()
  form.append('consent', 'true')
  form.append('capture_state', 'captured')
  form.append('file', file, 'selfie.jpg')
  return api.post(`/identity/verifications/${id}/selfie`, form, { onUploadProgress, timeout: 60000 })
}
export const issueLivenessChallenge = (id) => api.post(`/identity/verifications/${id}/liveness/challenge`)
export const submitLiveness = (id, challengeId, file, onUploadProgress) => {
  const form = new FormData()
  form.append('challenge_id', challengeId)
  form.append('consent', 'true')
  form.append('capture_state', 'completed_challenge')
  const extensions = {
    'video/webm': 'webm',
    'video/mp4': 'mp4',
    'video/quicktime': 'mov',
    'image/png': 'png',
    'image/jpeg': 'jpg',
  }
  const mimeType = file.type.split(';')[0]
  const extension = extensions[mimeType]
  if (!extension) throw new TypeError('Unsupported liveness capture format')
  form.append('file', file, `liveness-capture.${extension}`)
  return api.post(`/identity/verifications/${id}/liveness`, form, { onUploadProgress, timeout: 60000 })
}
export const livenessStatus = (id) => api.get(`/identity/verifications/${id}/liveness`)
