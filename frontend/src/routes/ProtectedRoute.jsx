import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/common/Button'

export function ProtectedRoute() {
  const { token, isLoading, authError, retrySession } = useAuth()
  const location = useLocation()
  if (isLoading) return <main className="mx-auto max-w-3xl px-6 py-16 text-center text-slate-500" role="status">Checking your session…</main>
  if (authError) return <main className="mx-auto max-w-3xl px-6 py-16"><p role="alert" className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{authError}</p><Button className="mt-4" onClick={retrySession}>Retry session check</Button></main>
  return token ? <Outlet /> : <Navigate to="/login" replace state={{ from: location.pathname }} />
}
