import { useState } from 'react'
import { api, money } from '../api'
import { AGENT_LABEL } from '../types'
import type { Approval } from '../types'

interface Props {
  approvals: Approval[]
  onDecided: () => void
  onError: (msg: string) => void
}

const KIND: Record<string, string> = { invoice: 'Vendor invoice', rent: 'Rent', purchase_order: 'Purchase order' }

/** The in-tray: payment slips the agents prepared. Nothing moves until a human stamps one. */
export default function ApprovalTray({ approvals, onDecided, onError }: Props) {
  const [name, setName] = useState(() => localStorage.getItem('approver') || 'Emilio Gonzalez')
  const [busy, setBusy] = useState<number | null>(null)
  const pending = approvals.filter((a) => a.status === 'pending')
  const decided = approvals.filter((a) => a.status !== 'pending').slice(-6).reverse()

  const decide = async (a: Approval, ok: boolean) => {
    setBusy(a.id)
    try {
      if (ok) await api.approve(a.id, name)
      else await api.reject(a.id, name)
      onDecided()
    } catch (e) {
      onError(`Approval #${a.id}: ${(e as Error).message}`)
      onDecided()
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="panel tray">
      <div className="panel-head">
        <h2 className="panel-title">In-tray {pending.length > 0 && <span className="count">{pending.length}</span>}</h2>
      </div>
      <label className="approver">
        Approving as
        <input
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            localStorage.setItem('approver', e.target.value)
          }}
        />
      </label>
      {pending.length === 0 && <p className="empty small">No payments waiting. Agents can only prepare them. You approve.</p>}
      {pending.map((a) => (
        <div key={a.id} className="slip">
          <div className="slip-head">
            <span>{KIND[a.kind] ?? a.kind} · #{a.id}</span>
            <span className="slip-amt">{money(a.amount)}</span>
          </div>
          <div className="slip-to">to {a.payee}</div>
          <div className="slip-why">{a.reason}</div>
          <div className="slip-meta">
            ticket #{a.ticket_id} · prepared by {AGENT_LABEL[a.requested_by] ?? a.requested_by}
          </div>
          <div className="slip-actions">
            <button className="approve" disabled={busy === a.id || !name.trim()} onClick={() => decide(a, true)}>
              Approve
            </button>
            <button className="ghost" disabled={busy === a.id} onClick={() => decide(a, false)}>
              Reject
            </button>
          </div>
        </div>
      ))}
      {decided.length > 0 && (
        <div className="decided">
          {decided.map((a) => (
            <div key={a.id} className={`done-slip d-${a.status}`}>
              <span className="mini-stamp">{a.status.toUpperCase()}</span>
              <span>
                {KIND[a.kind]} {money(a.amount)} · {a.payee}
              </span>
              <span className="by">{a.decided_by}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
