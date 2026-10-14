import type { Ticket } from '../types'

interface Props {
  tickets: Ticket[]
  selected: number | null
  onSelect: (id: number) => void
  onRun: (id: number) => void
}

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

function detail(t: Ticket): string {
  if (t.sku) return `${t.qty ?? '?'} × ${t.sku} · ${t.size}`
  if (t.lease_id) return `Lease #${t.lease_id}`
  return ''
}

/** The corkboard: one pinned index card per ticket. */
export default function TicketBoard({ tickets, selected, onSelect, onRun }: Props) {
  return (
    <section className="panel cork">
      <h2 className="panel-title">The board</h2>
      <div className="cards">
        {tickets.map((t, i) => (
          <article
            key={t.id}
            className={`card ${selected === t.id ? 'selected' : ''} status-${t.status}`}
            style={{ ['--tilt' as string]: `${[-1.2, 0.8, -0.5][i % 3]}deg` }}
            onClick={() => onSelect(t.id)}
          >
            <span className="pin" />
            <div className="card-head">
              <span className="ticket-no">#{t.id}</span>
              <span className="type">{TYPE_LABEL[t.type] ?? t.type}</span>
            </div>
            <h3>{t.subject}</h3>
            <p className="who">{t.requester}</p>
            <p className="note">{t.notes}</p>
            <p className="detail">{detail(t)}</p>
            <div className="card-foot">
              {t.status === 'resolved' ? (
                <span className="stamp resolved">RESOLVED</span>
              ) : t.status === 'awaiting_approval' ? (
                <span className="stamp waiting">NEEDS YOUR OK · {t.pending_approvals}</span>
              ) : t.running ? (
                <span className="working">
                  team working<span className="dots" />
                </span>
              ) : (
                <button
                  className="primary"
                  onClick={(e) => {
                    e.stopPropagation()
                    onRun(t.id)
                  }}
                >
                  Send in the team
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
