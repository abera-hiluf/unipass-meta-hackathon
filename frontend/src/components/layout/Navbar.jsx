import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { LogOut, Menu, X } from 'lucide-react'
import { Logo } from '../common/Logo'
import { Button } from '../common/Button'
import { useAuth } from '../../context/AuthContext'

export function Navbar() {
  const { token, user, signOut } = useAuth()
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const menuButtonRef = useRef(null)
  const location = useLocation()
  const links = token ? [['/dashboard', 'Dashboard'], ['/identity', 'Identity'], ['/profile', 'Profile'], ['/agentx', 'AgentX'], ...(user?.role === 'admin' ? [['/admin/reviews', 'Reviews']] : [])] : []

  useEffect(() => {
    setIsMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!isMenuOpen) return

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setIsMenuOpen(false)
        menuButtonRef.current?.focus()
      }
    }

    function handleResize() {
      if (window.matchMedia('(min-width: 768px)').matches) setIsMenuOpen(false)
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('resize', handleResize)
    }
  }, [isMenuOpen])

  function closeMenu() {
    setIsMenuOpen(false)
    menuButtonRef.current?.focus()
  }

  return <header className="border-b border-slate-200 bg-white/90 backdrop-blur"><div className="mx-auto max-w-7xl px-6"><div className="flex items-center justify-between py-4"><Logo /><nav aria-label="Primary navigation" className="hidden items-center gap-1 md:flex">{links.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-mist text-ink' : 'text-slate-500 hover:text-ink'}`}>{label}</NavLink>)}</nav><div className="flex items-center gap-2">{token ? <Button variant="ghost" onClick={signOut}><LogOut size={16} className="mr-2 inline" />Sign out</Button> : <><Link className="hidden rounded-xl px-4 py-2 text-sm font-semibold text-slate-600 sm:block" to="/login">Log in</Link><Link className="rounded-xl bg-ink px-4 py-2 text-sm font-semibold text-white" to="/register">Get started</Link></>}<button ref={menuButtonRef} type="button" className="grid h-10 w-10 place-items-center rounded-lg text-slate-600 hover:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-signal/40 md:hidden" aria-label={isMenuOpen ? 'Close navigation menu' : 'Open navigation menu'} aria-expanded={isMenuOpen} aria-controls={isMenuOpen ? 'mobile-navigation' : undefined} onClick={() => setIsMenuOpen((open) => !open)}>{isMenuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}</button></div></div>{isMenuOpen && <nav id="mobile-navigation" aria-label="Mobile navigation" className="space-y-1 border-t border-slate-100 py-3 md:hidden">{links.map(([to, label]) => <NavLink key={to} to={to} onClick={closeMenu} className={({ isActive }) => `block rounded-lg px-3 py-3 text-sm font-medium ${isActive ? 'bg-mist text-ink' : 'text-slate-600 hover:bg-slate-50 hover:text-ink'}`}>{label}</NavLink>)}{token ? null : <><Link to="/login" onClick={closeMenu} className="block rounded-lg px-3 py-3 text-sm font-medium text-slate-600 hover:bg-slate-50 hover:text-ink">Log in</Link><Link to="/register" onClick={closeMenu} className="block rounded-lg px-3 py-3 text-sm font-semibold text-signal hover:bg-slate-50">Get started</Link></>}</nav>}</div></header>
}
