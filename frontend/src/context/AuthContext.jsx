import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import * as auth from '../services/api/auth'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => sessionStorage.getItem('unipass_access_token'))
  const [user, setUser] = useState(null)

  useEffect(() => {
    const onUnauthorized = () => { setToken(null); setUser(null) }
    window.addEventListener('unipass:unauthorized', onUnauthorized)
    if (token) auth.me().then((response) => setUser(response.data)).catch(() => onUnauthorized())
    return () => window.removeEventListener('unipass:unauthorized', onUnauthorized)
  }, [token])

  const value = useMemo(() => ({
    token, user,
    async signIn(payload) {
      const response = await auth.login(payload)
      sessionStorage.setItem('unipass_access_token', response.data.access_token)
      setToken(response.data.access_token)
      return response.data
    },
    async signUp(payload) { return auth.register(payload) },
    signOut() { sessionStorage.removeItem('unipass_access_token'); setToken(null); setUser(null) },
  }), [token, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
