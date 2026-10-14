import { AGENTS } from '../types'
import type { AgentEvent, AgentName, Ticket } from '../types'

interface Props {
  events: AgentEvent[]
  running: boolean
  ticket: Ticket | null
}

const W = 560
const H = 330
const CX = W / 2
const CY = H / 2 + 8
const R = 128

// Pentagon, Boss at the top.
const POS: Record<AgentName, { x: number; y: number }> = Object.fromEntries(
  AGENTS.map((a, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / AGENTS.length
    return [a.name, { x: CX + R * 1.55 * Math.cos(angle), y: CY + R * Math.sin(angle) }]
  }),
) as Record<AgentName, { x: number; y: number }>

type Status = { label: string; mode: 'idle' | 'thinking' | 'tool' | 'waiting' | 'done' }

function statusOf(agent: string, events: AgentEvent[], running: boolean): Status {
  const mine = events.filter((e) => e.agent === agent)
  const last = mine[mine.length - 1]
  if (!last) return { label: 'idle', mode: 'idle' }
  if (!running) return { label: 'done', mode: 'done' }
  switch (last.kind) {
    case 'tool_call':
      return { label: last.tool ?? 'tool', mode: 'tool' }
    case 'delegation':
      return { label: `waiting on ${last.tool?.replace('_', ' ')}`, mode: 'waiting' }
    case 'agent_done':
    case 'run_done':
      return { label: 'reported back', mode: 'done' }
    default:
      return { label: 'thinking…', mode: 'thinking' }
  }
}

/** Five desks wired to each other (full connectivity). Delegations light up the wire between two desks. */
export default function TeamMap({ events, running, ticket }: Props) {
  const opened = new Map<string, number>()
  const closed = new Set<string>()
  for (const e of events) {
    if (e.kind === 'delegation' && e.tool) opened.set(`${e.agent}>${e.tool}`, (opened.get(`${e.agent}>${e.tool}`) ?? 0) + 1)
    if (e.kind === 'delegation_done' && e.tool) closed.add(`${e.agent}>${e.tool}`)
  }
  const activeEdges = [...opened.keys()].filter((k) => !closed.has(k) && running)
  const usedEdges = [...opened.keys()]

  const pairs: [AgentName, AgentName][] = []
  AGENTS.forEach((a, i) => AGENTS.slice(i + 1).forEach((b) => pairs.push([a.name, b.name])))

  return (
    <section className="panel teammap">
      <div className="panel-head">
        <h2 className="panel-title">The team {ticket ? <small>on ticket #{ticket.id}</small> : null}</h2>
        <span className="legend">
          <i className="l-used" /> delegated · <i className="l-live" /> live hand-off
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="map" role="img" aria-label="Agent delegation map">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--wire-live)" />
          </marker>
        </defs>
        {pairs.map(([a, b]) => (
          <line key={`${a}-${b}`} x1={POS[a].x} y1={POS[a].y} x2={POS[b].x} y2={POS[b].y} className="wire" />
        ))}
        {usedEdges.map((k) => {
          const [a, b] = k.split('>') as [AgentName, AgentName]
          if (!POS[a] || !POS[b]) return null
          const live = activeEdges.includes(k)
          return (
            <line
              key={k}
              x1={POS[a].x}
              y1={POS[a].y}
              x2={POS[b].x}
              y2={POS[b].y}
              className={live ? 'wire live' : 'wire used'}
              markerEnd={live ? 'url(#arrow)' : undefined}
            />
          )
        })}
        {AGENTS.map((a) => {
          const p = POS[a.name]
          const s = statusOf(a.name, events, running)
          return (
            <g key={a.name} className={`node n-${a.name} m-${s.mode}`} transform={`translate(${p.x},${p.y})`}>
              <circle r="34" className="halo" />
              <circle r="27" className="disc" />
              <text className="initials" y="6">
                {a.initials}
              </text>
              <text className="name" y="50">
                {a.label}
              </text>
              <text className="status" y="66">
                {s.label}
              </text>
            </g>
          )
        })}
      </svg>
    </section>
  )
}
