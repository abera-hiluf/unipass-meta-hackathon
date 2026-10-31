import { useEffect, useState } from 'react'
import { ArrowRight, CheckCircle2, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card } from '../components/common/Card'
import { Button } from '../components/common/Button'
import { StatusBadge } from '../components/common/StatusBadge'
import { Feedback } from '../components/common/Feedback'
import { useAuth } from '../context/AuthContext'
import { identityStatus } from '../services/api/identity'
import { myAffiliations } from '../services/api/institutions'
import { apiMessage } from '../services/api/client'

const stages = [['Account', 'Secure sign-in'], ['Institution', 'Verify eligibility'], ['Document', 'Submit identity document'], ['Selfie', 'Capture with consent'], ['Decision', 'Review explicit results']]

export function Dashboard() {
  const { user } = useAuth(); const [status, setStatus] = useState(null); const [affiliations, setAffiliations] = useState([]); const [error, setError] = useState(''); const [busy, setBusy] = useState(true)
  async function load() { setBusy(true); try { const [identity, affiliation] = await Promise.all([identityStatus(), myAffiliations()]); setStatus(identity.data); setAffiliations(affiliation.data); setError('') } catch (err) { setError(apiMessage(err)) } finally { setBusy(false) } }
  useEffect(() => { load() }, [])
  const currentAffiliation = affiliations[0]; const completed = [true, currentAffiliation?.status === 'enrollment_confirmed', Boolean(status?.verification_id && status?.document_analysis_status), false, status?.outcome === 'VERIFIED'].filter(Boolean).length
  return <main className="mx-auto max-w-7xl px-6 py-10"><div className="flex flex-wrap items-end justify-between gap-5"><div><p className="text-sm font-bold uppercase tracking-[.16em] text-signal">Student dashboard</p><h1 className="mt-2 text-4xl font-bold tracking-tight text-ink">Welcome back{user?.email ? `, ${user.email.split('@')[0]}` : ''}.</h1><p className="mt-3 text-slate-500">Your centralized identity journey, in one place.</p></div><Button variant="secondary" onClick={load} disabled={busy}><RefreshCw size={16} className="mr-2 inline" />Refresh</Button></div><div className="mt-6"><Feedback error={error} /></div><div className="mt-8 grid gap-5 lg:grid-cols-[1.4fr_.6fr]"><Card><div className="flex items-center justify-between"><div><p className="text-sm text-slate-500">Overall identity outcome</p><p className="mt-1 text-3xl font-bold text-ink">{busy ? 'Loading…' : status?.outcome || 'PENDING'}</p></div><CheckCircle2 className="text-signal" size={30} /></div><div className="mt-8 grid gap-4 md:grid-cols-5">{stages.map(([name, detail], index) => <div key={name}><div className={`grid h-9 w-9 place-items-center rounded-full text-sm font-bold ${index < completed ? 'bg-ink text-white' : 'bg-slate-100 text-slate-400'}`}>{index < completed ? '✓' : index + 1}</div><p className="mt-3 text-sm font-bold text-ink">{name}</p><p className="mt-1 text-xs leading-5 text-slate-500">{detail}</p></div>)}</div></Card><Card><p className="text-sm font-bold uppercase tracking-wide text-slate-400">Institution</p>{currentAffiliation ? <><h2 className="mt-3 text-lg font-bold text-ink">{currentAffiliation.institution_name}</h2><p className="mt-1 text-sm text-slate-500">{currentAffiliation.institutional_email}</p><div className="mt-5"><StatusBadge value={currentAffiliation.status} /></div></> : <p className="mt-4 text-sm leading-6 text-slate-500">No institution selected yet. Start from the identity workspace.</p>}</Card></div><div className="mt-5 grid gap-5 md:grid-cols-3"><StatusCard title="Document analysis" value={status?.document_analysis_status || 'NOT_STARTED'} /><StatusCard title="Liveness" value={status?.liveness_status || 'NOT_STARTED'} /><StatusCard title="Face match" value={status?.face_match_status || 'NOT_STARTED'} /></div><div className="mt-6 flex flex-wrap gap-3"><Link to="/identity"><Button>Continue identity verification <ArrowRight size={16} className="ml-2 inline" /></Button></Link><Link to="/profile"><Button variant="secondary">View profile</Button></Link></div></main>
}
function StatusCard({ title, value }) { return <Card><p className="text-sm text-slate-500">{title}</p><div className="mt-4"><StatusBadge value={value} /></div></Card> }
