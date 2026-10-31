import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import * as auth from '../services/api/auth'
import { apiMessage } from '../services/api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('unipass_access_token'))
  const [user, setUser] = useState(null)
  const [isLoading, setIsLoading] = useState(() => Boolean(sessionStorage.getItem('unipass_access_token')))
  const [authError, setAuthError] = useState('')
  const [sessionAttempt, setSessionAttempt] = useState(0)

  useEffect(() => {
    let active = true
    const onUnauthorized = () => {
      sessionStorage.removeItem('unipass_access_token')
      if (active) {
        setToken(null)
        setUser(null)
        setAuthError('')
        setIsLoading(false)
      }
    }

    window.addEventListener('unipass:unauthorized', onUnauthorized)
    if (!token) {
      setUser(null)
      setIsLoading(false)
    } else {
      setIsLoading(true)
      setAuthError('')
      auth.me().then((response) => {
        if (active) setUser(response.data)
      }).catch((error) => {
        if (error.response?.status === 401) {
          sessionStorage.removeItem('unipass_access_token')
          if (active) {
            setToken(null)
            setUser(null)
          }
        } else if (active) {
          setAuthError(apiMessage(error))
        }
      }).finally(() => {
        if (active) setIsLoading(false)
      })
    }

    return () => {
      active = false
      window.removeEventListener('unipass:unauthorized', onUnauthorized)
    }
  }, [token, sessionAttempt])

  const value = useMemo(() => ({
    token, user, isLoading, authError,
    async signIn(payload) {
      const response = await auth.login(payload)
      sessionStorage.setItem('unipass_access_token', response.data.access_token)
      setIsLoading(true)
      setAuthError('')
      setToken(response.data.access_token)
      return response.data
    },
    async signUp(payload) { return auth.register(payload) },
    signOut() { sessionStorage.removeItem('unipass_access_token'); setToken(null); setUser(null); setAuthError(''); setIsLoading(false) },
    retrySession() { setSessionAttempt((attempt) => attempt + 1) },
  }), [token, user, isLoading, authError])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
