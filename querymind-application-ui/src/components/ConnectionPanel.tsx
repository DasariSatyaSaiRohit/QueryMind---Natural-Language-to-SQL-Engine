import { useState } from 'react'
import api from '../lib/axios'
import { useStore } from '../store/usestore'

export function ConnectionPanel() {
  const [connStr, setConnStr] = useState('')
  const { session_id, database_name, session_status, setSession, setSessionStatus, clearSession, setLoading, addToast } = useStore()

  const handleConnect = async () => {
    if (!connStr.trim()) return
    setLoading(true, 'Connecting to database...')
    setSessionStatus('connecting')
    try {
      const res = await api.post('/session/connect', { connection_string: connStr })
      setSession(res.data.session_id, res.data.database_name ?? 'Database')
      addToast({ type: 'success', title: 'Connected', message: `Session started for ${res.data.database_name ?? 'database'}` })
      // Load history
      try {
        const hist = await api.get(`/query/history/${res.data.session_id}`)
        useStore.getState().setHistory(
          (hist.data.history ?? []).slice(0, 10).map((h: { sql: string; executed_at: string }) => ({
            question: h.sql,
            sql: h.sql,
            timestamp: h.executed_at,
          }))
        )
      } catch { /* history is non-critical */ }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Connection failed'
      addToast({ type: 'error', title: 'Connection Error', message: msg })
      setSessionStatus('disconnected')
    } finally {
      setLoading(false)
    }
  }

  const handleDisconnect = async () => {
    if (!session_id) return
    setLoading(true, 'Disconnecting...')
    try {
      await api.delete(`/session/${session_id}/disconnect`)
    } catch { /* silent */ } finally {
      clearSession()
      setConnStr('')
      setLoading(false)
      addToast({ type: 'info', title: 'Disconnected' })
    }
  }

  return (
    <div className="panel-section">
      <div className="section-title">Database Connection</div>
      {session_status !== 'connected' ? (
        <>
          <input
            className="conn-input"
            type="text"
            placeholder="postgresql://user:pass@host:5432/db"
            value={connStr}
            onChange={(e) => setConnStr(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
          />
          <button
            className="btn-connect"
            onClick={handleConnect}
            disabled={!connStr.trim() || session_status === 'connecting'}
          >
            {session_status === 'connecting' ? 'Connecting...' : 'Connect'}
          </button>
        </>
      ) : (
        <>
          <div className="conn-badge connected">
            <span className="conn-dot" />
            {database_name}
          </div>
          <button className="btn-disconnect" onClick={handleDisconnect}>
            Disconnect
          </button>
        </>
      )}
    </div>
  )
}