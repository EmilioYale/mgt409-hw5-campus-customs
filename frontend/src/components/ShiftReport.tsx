import { money } from '../api'
import { AGENTS, AGENT_LABEL } from '../types'
import type { Ticket, TicketSummary } from '../types'

interface Props {
  summary: TicketSummary | null
  ticket: Ticket | null
}

function firstLines(text: string, max = 420): string {
  const t = text.replace(/\*\*/g, '').trim()
  return t.length > max ? t.slice(0, max).trimEnd() + '…' : t
}

/** What each agent did on the selected ticket, plus the paperwork they left on the desk. */
export default function ShiftReport({ summary, ticket }: Props) {
  if (!ticket || !summary) {
    return (
      <section className="panel report">
        <h2 className="panel-title">Shift report</h2>
        <p className="empty">Select a ticket.</p>
      </section>
    )
  }
  const run = summary.run
  const work = summary.work
  const outcome = [...summary.updates].reverse().find((u) => u.agent === 'boss' && u.status !== 'note')

  return (
    <section className="panel report">
      <div className="panel-head">
        <h2 className="panel-title">
          Shift report <small>#{ticket.id}</small>
        </h2>
        <span className={`status-tag s-${ticket.status}`}>{ticket.status.replace('_', ' ')}</span>
      </div>

      {outcome && (
        <div className="outcome">
          <div className="outcome-label">Boss's call</div>
          <p>{firstLines(outcome.summary, 700)}</p>
        </div>
      )}

      {!run && !outcome && <p className="empty small">No run yet this session. Send in the team to see who does what.</p>}

      {run && (
        <div className="agent-cards">
          {AGENTS.filter((a) => run.agents[a.name]).map((a) => {
            const s = run.agents[a.name]
            return (
              <div key={a.name} className={`agent-card ac-${a.name}`}>
                <div className="ac-head">
                  <span className={`pill p-${a.name}`}>{a.label}</span>
                  <span className="tokens">{(s.input_tokens + s.output_tokens).toLocaleString()} tok</span>
                </div>
                {(s.called_by.length > 0 || s.delegated_to.length > 0) && (
                  <div className="ac-links">
                    {s.called_by.length > 0 && <>called by {s.called_by.map((c) => AGENT_LABEL[c]).join(', ')}</>}
                    {s.called_by.length > 0 && s.delegated_to.length > 0 && ' · '}
                    {s.delegated_to.length > 0 && <>handed to {[...new Set(s.delegated_to)].map((c) => AGENT_LABEL[c]).join(', ')}</>}
                  </div>
                )}
                <div className="ac-tools">
                  {s.tools_used.filter((t) => t !== 'delegate').map((t) => (
                    <code key={t}>{t}</code>
                  ))}
                </div>
                <p className="ac-summary">{s.summary ? firstLines(s.summary) : 'working…'}</p>
              </div>
            )
          })}
          {AGENTS.filter((a) => !run.agents[a.name]).length > 0 && (
            <p className="benched">
              Stayed at their desk: {AGENTS.filter((a) => !run.agents[a.name]).map((a) => a.label).join(', ')}
            </p>
          )}
        </div>
      )}

      {(work.quotes.length > 0 || work.purchase_orders.length > 0 || work.reservations.length > 0) && (
        <div className="paperwork">
          <h3>Paperwork</h3>
          <ul>
            {work.quotes.map((q) => (
              <li key={`q${q.id}`}>
                Quote: {q.qty} × {q.sku} at {money(q.unit_price)} ({q.discount_pct}% off) · margin {money(q.margin_per_unit)}/unit · {money(q.total)}
              </li>
            ))}
            {work.purchase_orders.map((p) => (
              <li key={`p${p.id}`}>
                PO #{p.id}: {p.qty} × {p.sku} {p.size} · {money(p.total)} · ETA {p.eta} · <b>{p.status.replace('_', ' ')}</b>
              </li>
            ))}
            {work.reservations.map((r) => (
              <li key={`r${r.id}`}>
                Held on shelf: {r.qty} × {r.sku} {r.size}
              </li>
            ))}
          </ul>
        </div>
      )}

      {work.drafts.map((d) => (
        <div key={d.id} className="letter">
          <div className="letter-head">
            <span>DRAFT · not sent</span>
            <span>by {AGENT_LABEL[d.created_by] ?? d.created_by}</span>
          </div>
          <div className="letter-to">To: {d.to_name}</div>
          <div className="letter-subj">{d.subject}</div>
          <p className="letter-body">{d.body}</p>
        </div>
      ))}
    </section>
  )
}
