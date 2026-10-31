import { useEffect, useState } from 'react'
import { Construction, ShieldCheck } from 'lucide-react'
import { Card } from '../components/common/Card'
import { Feedback } from '../components/common/Feedback'
import { useAuth } from '../context/AuthContext'
import { identityStatus } from '../services/api/identity'
import { myAffiliations } from '../services/api/institutions'
import { apiMessage } from '../services/api/client'

export function Placeholder({ title, detail }) { return <main className="mx-auto max-w-4xl px-6 py-16"><Card><Construction className="text-signal" size={28} /><h1 className="mt-5 text-3xl font-bold text-ink">{title}</h1><p className="mt-3 max-w-xl leading-7 text-slate-500">{detail}</p></Card></main> }

export function Profile() {
  const { user } = useAuth(); const [status, setStatus] = useState(null); const [affiliation, setAffiliation] = useState(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(true)
  useEffect(() => { Promise.all([identityStatus(), myAffiliations()]).then(([identity, affiliations]) => { setStatus(identity.data); setAffiliation(affiliations.data[0]) }).catch((err) => setError(apiMessage(err))).finally(() => setLoading(false)) }, [])
  const pendingValue = loading ? 'Loading…' : error ? 'Unavailable' : 'Not available'
  return <main className="mx-auto max-w-5xl px-6 py-10"><p className="text-sm font-bold uppercase tracking-[.16em] text-signal">Account</p><h1 className="mt-2 text-4xl font-bold text-ink">Your profile</h1><p className="mt-3 text-slate-500">Only data returned by the backend is shown here.</p><div className="mt-6"><Feedback error={error} /></div><div className="mt-8 grid gap-5 md:grid-cols-2"><Card><div className="flex items-center gap-3"><ShieldCheck className="text-signal" /><h2 className="text-lg font-bold text-ink">Account information</h2></div><dl className="mt-6 space-y-4 text-sm"><ProfileRow label="Email" value={user?.email} /><ProfileRow label="Account role" value={user?.role} /><ProfileRow label="Account status" value={user ? (user.is_active ? 'Active' : 'Inactive') : pendingValue} /></dl></Card><Card><h2 className="text-lg font-bold text-ink">Identity claims</h2><dl className="mt-6 space-y-4 text-sm"><ProfileRow label="Institution" value={affiliation?.institution_name || (error ? 'Unavailable' : 'Not selected')} /><ProfileRow label="Enrollment" value={affiliation?.status || pendingValue} /><ProfileRow label="Identity outcome" value={status?.outcome || (loading ? 'Loading…' : error ? 'Unavailable' : 'PENDING')} /></dl></Card></div><Card className="mt-5"><h2 className="text-lg font-bold text-ink">Profile settings</h2><p className="mt-3 text-sm leading-6 text-slate-500">Profile updates, consent management, and account-deletion requests are not implemented by the current backend. No nonfunctional save controls are shown.</p></Card></main>
}
function ProfileRow({ label, value }) { return <div className="flex items-center justify-between gap-4 border-b border-slate-100 pb-3"><dt className="text-slate-400">{label}</dt><dd className="text-right font-semibold text-ink">{value || 'Unavailable'}</dd></div> }
