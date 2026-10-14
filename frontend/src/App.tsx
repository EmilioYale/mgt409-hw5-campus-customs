import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from './api'
import type { AgentEvent, Approval, Cash, Ticket, TicketSummary } from './types'
import TopBar from './components/TopBar'
import TicketBoard from './components/TicketBoard'
import TeamMap from './components/TeamMap'
import LiveFeed from './components/LiveFeed'
import ApprovalTray from './components/ApprovalTray'
import ShiftReport from './components/ShiftReport'

function initialTicket(): number | null {
  const fromUrl = Number(new URLSearchParams(window.location.search).get('ticket'))
  return Number.isFinite(fromUrl) && fromUrl > 0 ? fromUrl : null
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [selected, setSelected] = useState<number | null>(initialTicket)
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [online, setOnline] = useState(true)
  const lastSeq = useRef(0)

  const refresh = useCallback(async () => {
    try {
      const [t, c, a] = await Promise.all([api.tickets(), api.cash(), api.approvals()])
      setTickets(t)
      setCash(c)
      setApprovals(a)
      setOnline(true)
    } catch {
      setOnline(false)
    }
  }, [])

  const pollEvents = useCallback(async () => {
    try {
      const r = await api.events(lastSeq.current)
      if (r.events.length) {
        lastSeq.current = r.last_seq
        setEvents((prev) => [...prev, ...r.events].slice(-3000))
      }
    } catch {
      /* offline banner comes from refresh() */
    }
  }, [])

  useEffect(() => {
    refresh()
    pollEvents()
    const a = setInterval(refresh, 2000)
    const b = setInterval(pollEvents, 1000)
    return () => {
      clearInterval(a)
      clearInterval(b)
    }
  }, [refresh, pollEvents])

  // Default selection: first open ticket.
  useEffect(() => {
    if (selected === null && tickets.length) setSelected(tickets[0].id)
  }, [tickets, selected])

  // Per-ticket summary, refreshed while the ticket is on screen.
  useEffect(() => {
    if (selected === null) return
    let alive = true
    const load = () => api.summary(selected).then((s) => alive && setSummary(s)).catch(() => {})
    load()
    const t = setInterval(load, 2000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [selected])

  const selectedTicket = tickets.find((t) => t.id === selected) || null

  // Only show the latest run of the selected ticket.
  const runEvents = useMemo(() => {
    const mine = events.filter((e) => e.ticket_id === selected)
    const lastStart = [...mine].reverse().find((e) => e.kind === 'run_started')
    return lastStart ? mine.filter((e) => e.run_id === lastStart.run_id) : mine
  }, [events, selected])

  const startRun = async (id: number) => {
    setError(null)
    setSelected(id)
    try {
      await api.run(id)
      refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const resetDb = async () => {
    if (!window.confirm('Reset campus_customs_new.db to the original values? Approvals, drafts and payments on the board will be cleared.')) return
    try {
      await api.reset()
      setEvents([])
      setSummary(null)
      refresh()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="desk">
      <TopBar cash={cash} online={online} onReset={resetDb} />
      {error && (
        <div className="banner error" onClick={() => setError(null)}>
          {error} <span className="dismiss">dismiss</span>
        </div>
      )}
      {!online && <div className="banner warn">Can't reach the backend at localhost:8000. Is uvicorn running?</div>}
      <main className="layout">
        <aside className="col-left">
          <TicketBoard tickets={tickets} selected={selected} onSelect={setSelected} onRun={startRun} />
          <ApprovalTray approvals={approvals} onDecided={refresh} onError={setError} />
        </aside>
        <section className="col-center">
          <TeamMap events={runEvents} running={!!selectedTicket?.running} ticket={selectedTicket} />
          <LiveFeed events={runEvents} running={!!selectedTicket?.running} />
        </section>
        <aside className="col-right">
          <ShiftReport summary={summary} ticket={selectedTicket} />
        </aside>
      </main>
    </div>
  )
}
