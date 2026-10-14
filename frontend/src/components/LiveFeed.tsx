import { useEffect, useRef } from 'react'
import { AGENT_LABEL } from '../types'
import type { AgentEvent } from '../types'

interface Props {
  events: AgentEvent[]
  running: boolean
}

function argText(args: Record<string, unknown> | null): string {
  if (!args) return ''
  return Object.entries(args)
    .filter(([k]) => !['created_by', 'requested_by', 'agent'].includes(k))
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
}

function Line({ e }: { e: AgentEvent }) {
  const who = <span className={`pill p-${e.agent}`}>{AGENT_LABEL[e.agent] ?? e.agent}</span>
  switch (e.kind) {
    case 'run_started':
      return <div className="line sys">— {e.text} —</div>
    case 'user_prompt':
      return e.depth > 0 ? (
        <div className="line">
          {who} <span className="muted">picked up the task from {AGENT_LABEL[e.called_by ?? ''] ?? e.called_by}</span>
        </div>
      ) : null
    case 'model_response':
      return e.text ? (
        <div className="line says">
          {who} <span className="speech">{e.text}</span>
        </div>
      ) : null
    case 'tool_call':
      return (
        <div className="line tool">
          {who} <code className="toolname">{e.tool}</code> <span className="args">{argText(e.args)}</span>
        </div>
      )
    case 'tool_result':
      return (
        <details className="line result">
          <summary>
            <span className="arrow">↳</span> {e.tool} returned
          </summary>
          <pre>{e.result}</pre>
        </details>
      )
    case 'delegation':
      return (
        <div className="line handoff">
          {who} <span className="hand">hands off to</span> <span className={`pill p-${e.tool}`}>{AGENT_LABEL[e.tool ?? ''] ?? e.tool}</span>
          <div className="task">“{e.text}”</div>
        </div>
      )
    case 'delegation_done':
      return (
        <div className="line handback">
          <span className={`pill p-${e.tool}`}>{AGENT_LABEL[e.tool ?? ''] ?? e.tool}</span> <span className="hand">reported back to</span> {who}
        </div>
      )
    case 'agent_done':
      return null
    case 'run_done':
      return <div className="line sys done">— run finished · {String(e.usage?.total_tokens ?? 0)} tokens —</div>
    case 'error':
      return <div className="line err">⚠ {e.text}</div>
    default:
      return null
  }
}

/** The chatter: what each agent says and every tool it touches, in order. */
export default function LiveFeed({ events, running }: Props) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight
  }, [events.length])

  return (
    <section className="panel feed">
      <div className="panel-head">
        <h2 className="panel-title">Desk chatter</h2>
        {running && <span className="live-dot">live</span>}
      </div>
      <div className="feed-body" ref={box}>
        {events.length === 0 ? (
          <p className="empty">Pick a ticket and press <b>Send in the team</b>. Every message, hand-off and tool call shows up here.</p>
        ) : (
          events.map((e) => <Line key={e.seq} e={e} />)
        )}
      </div>
    </section>
  )
}
