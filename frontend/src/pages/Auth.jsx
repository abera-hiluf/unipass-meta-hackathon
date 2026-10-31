import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { useAuth } from '../context/AuthContext'
import { apiMessage } from '../services/api/client'

export function Auth({ mode }) {
  const isLogin = mode === 'login'; const { signIn, signUp } = useAuth(); const navigate = useNavigate(); const location = useLocation()
  const [form, setForm] = useState({ email: '', password: '' }); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function submit(event) { event.preventDefault(); setBusy(true); setError(''); try { if (isLogin) await signIn(form); else await signUp(form); navigate(isLogin ? (location.state?.from || '/dashboard') : '/login') } catch (err) { setError(apiMessage(err)) } finally { setBusy(false) } }
  return <main className="mx-auto flex min-h-[calc(100vh-73px)] max-w-7xl items-center justify-center px-6 py-16"><Card className="w-full max-w-md"><p className="text-sm font-bold uppercase tracking-[.16em] text-signal">UniPass AI</p><h1 className="mt-3 text-3xl font-bold text-ink">{isLogin ? 'Welcome back' : 'Create your account'}</h1><p className="mt-2 text-sm text-slate-500">{isLogin ? 'Continue your identity journey.' : 'Account creation does not verify identity or enrollment.'}</p><form onSubmit={submit} className="mt-8 space-y-5"><label className="block text-sm font-semibold text-ink">Email<input required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 outline-none focus:border-signal" /></label><label className="block text-sm font-semibold text-ink">Password<input required minLength="8" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} className="mt-2 w-full rounded-xl border border-slate-200 px-4 py-3 outline-none focus:border-signal" /></label>{error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}<Button disabled={busy} className="w-full">{busy ? 'Working…' : isLogin ? 'Log in' : 'Create account'}</Button></form><p className="mt-6 text-center text-sm text-slate-500">{isLogin ? <>Need an account? <Link className="font-semibold text-signal" to="/register">Register</Link></> : <>Already registered? <Link className="font-semibold text-signal" to="/login">Log in</Link></>}</p></Card></main>
}
