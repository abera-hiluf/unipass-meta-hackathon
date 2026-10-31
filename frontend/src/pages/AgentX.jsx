import { Bot, Clock3 } from 'lucide-react'
import { Card } from '../components/common/Card'

export function AgentX() {
  return <main className="mx-auto max-w-4xl px-6 py-10">
    <div>
      <p className="text-sm font-bold uppercase tracking-[.16em] text-signal">AgentX</p>
      <h1 className="mt-2 text-4xl font-bold text-ink">Your campus identity companion</h1>
      <p className="mt-3 text-slate-500">AgentX execution is not yet available.</p>
    </div>
    <Card className="mt-8 overflow-hidden">
      <div className="relative grid min-h-[360px] place-items-center bg-gradient-to-br from-white via-white to-blue-50 px-6 py-12 text-center">
        <div className="max-w-lg">
          <div className="mx-auto grid h-16 w-16 place-items-center rounded-2xl bg-ink text-white shadow-lg shadow-ink/15">
            <Bot size={28} aria-hidden="true" />
          </div>
          <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-signal">
            <Clock3 size={14} aria-hidden="true" />
            Coming soon
          </div>
          <h2 className="mt-4 text-2xl font-bold text-ink">AgentX is not available yet</h2>
          <p className="mt-3 text-sm leading-6 text-slate-500">The assistant cannot execute campus services at this time. No messages are sent and no campus-service actions are performed from this page.</p>
        </div>
      </div>
    </Card>
  </main>
}
