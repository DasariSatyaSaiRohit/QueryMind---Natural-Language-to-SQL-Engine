import { create } from 'zustand'

/* ── Types ──────────────────────────────────────────────────────────── */
export interface User {
  user_id: string
  email: string
}

export interface RAGContext {
  selected_tables: string[]
  total_tables: number
  tables_injected: number
}

export interface ValidationInfo {
  passed: boolean
  failed_pass?: number
  reason?: string
  invalid_references?: string[]
}

export interface Column { name: string }

export interface ResultsObject {
  columns: Column[]
  rows: unknown[][]
  pagination: {
    page: number
    page_size: number
    total_rows: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
  truncated: boolean
  truncation_warning?: string
}

export interface Toast {
  id: string
  type: 'success' | 'error' | 'info'
  title: string
  message?: string
  exiting?: boolean
}

export interface HistoryItem {
  question: string
  sql: string
  timestamp: string
}

/* ── Store Shape ─────────────────────────────────────────────────────── */
interface Store {
  // Auth
  access_token: string | null
  refresh_token: string | null
  user: User | null
  setAuth: (access: string, refresh: string, user: User) => void
  clearAuth: () => void

  // Session
  session_id: string | null
  database_name: string | null
  session_status: 'disconnected' | 'connecting' | 'connected'
  setSession: (id: string, name: string) => void
  setSessionStatus: (s: 'disconnected' | 'connecting' | 'connected') => void
  clearSession: () => void

  // Query
  question: string
  query_status: 'idle' | 'streaming' | 'complete' | 'error'
  streaming_text: string
  rag_context: RAGContext | null
  sql: string | null
  rationale: string | null
  explanation: string | null
  tables_used: string[]
  validation: ValidationInfo | null
  generation_time_ms: number | null
  cache_hit: boolean
  results: ResultsObject | null
  query_error: string | null
  error_type: string | null

  setQuestion: (q: string) => void
  setQueryStatus: (s: 'idle' | 'streaming' | 'complete' | 'error') => void
  setStreamingText: (t: string) => void
  appendStreamingText: (chunk: string) => void
  setRAGContext: (ctx: RAGContext) => void
  setQueryComplete: (payload: {
    sql: string
    rationale: string
    explanation: string
    tables_used: string[]
    validation: ValidationInfo
    generation_time_ms: number
    cache_hit: boolean
  }) => void
  setResults: (r: ResultsObject) => void
  setQueryError: (msg: string, type?: string) => void
  resetQuery: () => void

  // History
  history: HistoryItem[]
  addHistory: (item: HistoryItem) => void
  setHistory: (items: HistoryItem[]) => void

  // Toast
  toasts: Toast[]
  addToast: (t: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void

  // Loading overlay
  loading: boolean
  loadingText: string
  setLoading: (v: boolean, text?: string) => void
}

/* ── Store Implementation ────────────────────────────────────────────── */
export const useStore = create<Store>((set) => ({
  // Auth
  access_token: null,
  refresh_token: null,
  user: null,
  setAuth: (access, refresh, user) => set({ access_token: access, refresh_token: refresh, user }),
  clearAuth: () => set({ access_token: null, refresh_token: null, user: null }),

  // Session
  session_id: null,
  database_name: null,
  session_status: 'disconnected',
  setSession: (id, name) => set({ session_id: id, database_name: name, session_status: 'connected' }),
  setSessionStatus: (s) => set({ session_status: s }),
  clearSession: () => set({ session_id: null, database_name: null, session_status: 'disconnected', results: null }),

  // Query
  question: '',
  query_status: 'idle',
  streaming_text: '',
  rag_context: null,
  sql: null,
  rationale: null,
  explanation: null,
  tables_used: [],
  validation: null,
  generation_time_ms: null,
  cache_hit: false,
  results: null,
  query_error: null,
  error_type: null,

  setQuestion: (q) => set({ question: q }),
  setQueryStatus: (s) => set({ query_status: s }),
  setStreamingText: (t) => set({ streaming_text: t }),
  appendStreamingText: (chunk) => set((state) => ({ streaming_text: state.streaming_text + chunk })),
  setRAGContext: (ctx) => set({ rag_context: ctx }),
  setQueryComplete: (payload) => set({
    query_status: 'complete',
    sql: payload.sql,
    rationale: payload.rationale,
    explanation: payload.explanation,
    tables_used: payload.tables_used,
    validation: payload.validation,
    generation_time_ms: payload.generation_time_ms,
    cache_hit: payload.cache_hit,
  }),
  setResults: (r) => set({ results: r }),
  setQueryError: (msg, type) => set({ query_status: 'error', query_error: msg, error_type: type ?? null }),
  resetQuery: () => set({
    query_status: 'idle',
    streaming_text: '',
    rag_context: null,
    sql: null,
    rationale: null,
    explanation: null,
    tables_used: [],
    validation: null,
    generation_time_ms: null,
    cache_hit: false,
    results: null,
    query_error: null,
    error_type: null,
  }),

  // History
  history: [],
  addHistory: (item) => set((state) => ({ history: [item, ...state.history].slice(0, 10) })),
  setHistory: (items) => set({ history: items }),

  // Toast
  toasts: [],
  addToast: (t) => {
    const id = Math.random().toString(36).slice(2)
    set((state) => ({ toasts: [...state.toasts, { ...t, id }] }))
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.map((x) => x.id === id ? { ...x, exiting: true } : x)
      }))
      setTimeout(() => {
        set((state) => ({ toasts: state.toasts.filter((x) => x.id !== id) }))
      }, 300)
    }, 4000)
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  // Loading
  loading: false,
  loadingText: '',
  setLoading: (v, text = '') => set({ loading: v, loadingText: text }),
}))