import { api } from './client'

export const listInstitutions = () => api.get('/institutions')
export const myAffiliations = () => api.get('/institutions/me')
export const myInstitutionSelection = () => api.get('/institutions/me/selection')
export const saveInstitutionSelection = (institution_id) => api.post('/institutions/me/selection', { institution_id })
export const requestEmailVerification = (institutionId, payload) => api.post(`/institutions/${institutionId}/email-verification`, payload)
export const confirmEmailVerification = (payload) => api.post('/institutions/email-verification/confirm', payload)
export const verifyEligibility = (affiliationId, payload) => api.post(`/affiliations/${affiliationId}/verify-eligibility`, payload)
