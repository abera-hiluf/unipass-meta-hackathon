import { Link, NavLink } from 'react-router-dom'
import { LogOut, Menu } from 'lucide-react'
import { Logo } from '../common/Logo'
import { Button } from '../common/Button'
import { useAuth } from '../../context/AuthContext'

export function Navbar() {
  const { token, signOut } = useAuth()
  const links = token ? [['/dashboard', 'Dashboard'], ['/identity', 'Identity'], ['/profile', 'Profile'], ['/agentx', 'AgentX']] : []
  return <header className="border-b border-slate-200 bg-white/90 backdrop-blur"><div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4"><Logo /><nav className="hidden items-center gap-1 md:flex">{links.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-mist text-ink' : 'text-slate-500 hover:text-ink'}`}>{label}</NavLink>)}</nav><div className="flex items-center gap-2">{token ? <Button variant="ghost" onClick={signOut}><LogOut size={16} className="mr-2 inline" />Sign out</Button> : <><Link className="hidden rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 sm:block" to="/login">Log in</Link><Link className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white" to="/register">Get started</Link></>}<Menu className="text-slate-400 md:hidden" size={20} /></div></div></header>
}
