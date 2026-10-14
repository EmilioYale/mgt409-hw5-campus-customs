export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'

export const AGENTS: { name: AgentName; label: string; role: string; initials: string }[] = [
  { name: 'boss', label: 'Boss', role: 'reads tickets, makes the call', initials: 'BO' },
  { name: 'inventory', label: 'Inventory', role: 'stock, sizes, vendors', initials: 'IN' },
  { name: 'accounting', label: 'Accounting', role: 'cash, invoices, margins', initials: 'AC' },
  { name: 'facilities', label: 'Facilities', role: 'leases & rent', initials: 'FA' },
  { name: 'customer_service', label: 'Customer Service', role: 'drafts to customers', initials: 'CS' },
]

export const AGENT_LABEL: Record<string, string> = Object.fromEntries(AGENTS.map((a) => [a.name, a.label]))

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: 'open' | 'awaiting_approval' | 'resolved' | string
  notes: string | null
  created_at: string
  is_resolved: boolean
  running: boolean
  pending_approvals: number
}

export interface AgentEvent {
  seq: number
  ts: string
  run_id: string
  ticket_id: number
  agent: string
  kind:
    | 'run_started' | 'user_prompt' | 'model_request' | 'model_response' | 'tool_call' | 'tool_result'
    | 'delegation' | 'delegation_done' | 'agent_done' | 'run_done' | 'error'
  depth: number
  called_by: string | null
  text: string
  tool: string | null
  args: Record<string, unknown> | null
  result: string | null
  usage: Record<string, unknown> | null
}

export interface Approval {
  id: number
  ticket_id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number
  payee: string
  amount: number
  reason: string | null
  requested_by: string
  status: 'pending' | 'approved' | 'rejected' | 'refused'
  created_at: string
  decided_at: string | null
  decided_by: string | null
  result: string | null
}

export interface Payment {
  id: number
  kind: string
  ref_id: number
  amount: number
  account: string
  paid_at: string
  approved_by: string
}

export interface Cash {
  account: string
  balance: number
  as_of: string
  pending_approval_total: number
  available_after_pending: number
  payments: Payment[]
}

export interface AgentSummary {
  agent: string
  runs: number
  tools_used: string[]
  delegated_to: string[]
  called_by: string[]
  summary: string
  input_tokens: number
  output_tokens: number
}

export interface TicketRun {
  run_id: string
  ticket_id: number
  status: 'running' | 'finished' | 'error'
  started_at: string
  finished_at: string | null
  final: string
  error: string | null
  agents: Record<string, AgentSummary>
  delegations: { from: string; to: string; task: string; depth: number; status: string; reply?: string }[]
  total_tokens: number
}

export interface Draft {
  id: number
  ticket_id: number
  to_name: string
  subject: string
  body: string
  created_by: string
  created_at: string
}

export interface TicketSummary {
  ticket: Ticket
  updates: { agent: string; status: string; summary: string; created_at: string }[]
  run: TicketRun | null
  running: boolean
  work: {
    quotes: { id: number; sku: string; qty: number; discount_pct: number; unit_price: number; unit_cost: number; margin_per_unit: number; total: number }[]
    purchase_orders: { id: number; vendor_id: number; sku: string; size: string; qty: number; total: number; eta: string; status: string }[]
    reservations: { id: number; sku: string; size: string; qty: number }[]
    drafts: Draft[]
    approvals: Approval[]
    updates: { agent: string; status: string; summary: string; created_at: string }[]
  }
}
