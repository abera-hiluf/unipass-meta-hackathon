import { ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'

export function Logo() {
  return <Link to="/" className="flex items-center gap-2 font-bold tracking-tight text-ink"><span className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-white"><ShieldCheck size={20} /></span><span>UniPass <span className="text-signal">AI</span></span></Link>
}
