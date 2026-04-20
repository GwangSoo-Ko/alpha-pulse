export type User = {
  id: number
  email: string
  role: string
}

export type RunSummary = {
  run_id: string
  name: string
  strategies: string[]
  start_date: string
  end_date: string
  initial_capital: number
  final_value: number
  benchmark: string
  metrics: Record<string, number>
  created_at: number
}

export type RunDetail = RunSummary & {
  params: Record<string, unknown>
}

export type RunList = {
  items: RunSummary[]
  page: number
  size: number
  total: number
}

export type Snapshot = {
  date: string
  cash: number
  total_value: number
  daily_return: number
  cumulative_return: number
  drawdown: number
}

export type Trade = {
  code: string
  name: string
  buy_date: string
  buy_price: number
  sell_date: string
  sell_price: number
  quantity: number
  pnl: number
  return_pct: number
  holding_days: number
  commission: number
  tax: number
  strategy_id: string
}

export type Position = {
  date: string
  code: string
  name: string
  quantity: number
  avg_price: number
  current_price: number
  unrealized_pnl: number
  weight: number
  strategy_id: string
}

export type Job = {
  id: string
  kind: string
  status: "pending" | "running" | "done" | "failed" | "cancelled"
  progress: number
  progress_text: string
  result_ref: string | null
  error: string | null
  created_at: number
  started_at: number | null
  finished_at: number | null
}
