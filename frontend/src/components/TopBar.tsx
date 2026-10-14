import { useEffect, useRef, useState } from 'react'
import { money } from '../api'
import type { Cash } from '../types'

interface Props {
  cash: Cash | null
  online: boolean
  onReset: () => void
}

/** Brand strip + the cash register. The register flashes the drop after each approved payment. */
export default function TopBar({ cash, online, onReset }: Props) {
  const prev = useRef<number | null>(null)
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null)

  useEffect(() => {
    if (!cash) return
    if (prev.current !== null && cash.balance < prev.current) {
      setDrop({ amount: prev.current - cash.balance, key: Date.now() })
    }
    prev.current = cash.balance
  }, [cash])

  return (
    <header className="topbar">
      <div className="brand">
        <div className="crest">CC</div>
        <div>
          <h1>Campus Customs</h1>
          <p>Chapel Street Desk · multi-agent ops</p>
        </div>
      </div>
      <div className="meta">
        <span className="chip">shop date {cash?.as_of ?? '…'}</span>
        <span className="chip">gpt-6-luna via Portkey</span>
        <span className={`chip ${online ? 'ok' : 'bad'}`}>{online ? 'backend live' : 'backend offline'}</span>
        <button className="ghost" onClick={onReset} title="Copy campus_customs.db over the working copy">
          Reset DB
        </button>
      </div>
      <div className="register" aria-label="Checking balance">
        <div className="register-label">CHECKING</div>
        <div className="register-screen">
          <span className="balance">{cash ? money(cash.balance) : '—'}</span>
          {drop && (
            <span key={drop.key} className="drop">
              −{money(drop.amount)}
            </span>
          )}
        </div>
        <div className="register-sub">
          {cash && cash.pending_approval_total > 0
            ? `${money(cash.pending_approval_total)} waiting on approval · ${money(cash.available_after_pending)} free`
            : 'nothing pending'}
        </div>
      </div>
    </header>
  )
}
