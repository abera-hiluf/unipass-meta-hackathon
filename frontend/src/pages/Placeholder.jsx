import { Construction } from 'lucide-react'
import { Card } from '../components/common/Card'
export function Placeholder({ title, detail }) { return <main className="mx-auto max-w-4xl px-6 py-16"><Card><Construction className="text-signal" size={28} /><h1 className="mt-5 text-3xl font-bold text-ink">{title}</h1><p className="mt-3 max-w-xl leading-7 text-slate-500">{detail}</p></Card></main> }
