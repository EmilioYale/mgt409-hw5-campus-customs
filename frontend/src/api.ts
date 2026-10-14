import type { AgentEvent, Approval, Cash, Ticket, TicketSummary } from './types'

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') || 'http://localhost:8000'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body?.detail || `${res.status} ${res.statusText}`)
  return body as T
}

export const api = {
  health: () => req<{ ok: boolean; model: string; db: string }>('/api/health'),
  tickets: () => req<{ tickets: Ticket[] }>('/api/tickets').then((r) => r.tickets),
  run: (id: number) => req<{ ok: boolean }>(`/api/tickets/${id}/run`, { method: 'POST' }),
  events: (since: number) => req<{ events: AgentEvent[]; last_seq: number }>(`/api/events?since=${since}`),
  summary: (id: number) => req<TicketSummary>(`/api/tickets/${id}/summary`),
  approvals: () => req<{ approvals: Approval[] }>('/api/approvals').then((r) => r.approvals),
  approve: (id: number, approved_by: string) =>
    req<{ ok: boolean; balance_after: number; effect: string }>(`/api/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by }),
    }),
  reject: (id: number, approved_by: string) =>
    req<{ ok: boolean }>(`/api/approvals/${id}/reject`, { method: 'POST', body: JSON.stringify({ approved_by }) }),
  cash: () => req<Cash>('/api/cash'),
  reset: () => req<{ ok: boolean; message: string }>('/api/reset', { method: 'POST' }),
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })
