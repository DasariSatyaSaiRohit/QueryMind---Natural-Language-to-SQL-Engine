import { useRef, useCallback } from 'react'
import { useStore } from '../store/usestore'

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const store = useStore()

  const close = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const connect = useCallback((sessionId: string, token: string, question: string) => {
    // Close any existing connection first
    close()

    store.resetQuery()
    store.setQueryStatus('streaming')
    store.setStreamingText('')

    const url = `ws://localhost:8000/ws/query/${sessionId}?token=${token}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ question, session_id: sessionId }))
    }

    ws.onmessage = (event) => {
      const raw: string = event.data

      // Terminal result frame from AI Service
      if (raw.startsWith('__RESULT__:')) {
        try {
          const result = JSON.parse(raw.slice('__RESULT__:'.length))
          if (result.success) {
            store.setQueryComplete({
              sql: result.sql,
              rationale: result.rationale ?? '',
              explanation: result.explanation ?? '',
              tables_used: result.tables_used ?? [],
              validation: result.validation ?? { passed: true },
              generation_time_ms: result.latency_ms ?? 0,
              cache_hit: result.cache_hit ?? false,
            })
            // Add to history
            store.addHistory({
              question,
              sql: result.sql,
              timestamp: new Date().toISOString(),
            })
          } else {
            store.setQueryError(result.error ?? 'Generation failed', result.error_type)
          }
        } catch {
          store.setQueryError('Failed to parse server response')
        }
        return
      }

      // Structured JSON frames
      try {
        const msg = JSON.parse(raw)

        if (msg.type === 'rag_context') {
          store.setRAGContext({
            selected_tables: msg.selected_tables ?? [],
            total_tables: msg.total_tables ?? 0,
            tables_injected: msg.tables_injected ?? 0,
          })
          return
        }

        if (msg.type === 'cache_hit') {
          store.setQueryComplete({
            sql: msg.sql,
            rationale: msg.rationale ?? '',
            explanation: msg.explanation ?? '',
            tables_used: msg.tables_used ?? [],
            validation: { passed: true },
            generation_time_ms: 0,
            cache_hit: true,
          })
          store.addHistory({ question, sql: msg.sql, timestamp: new Date().toISOString() })
          return
        }

        if (msg.type === 'complete') {
          store.setQueryComplete({
            sql: msg.sql,
            rationale: msg.rationale ?? '',
            explanation: msg.explanation ?? '',
            tables_used: msg.tables_used ?? [],
            validation: msg.validation ?? { passed: true },
            generation_time_ms: msg.generation_time_ms ?? 0,
            cache_hit: msg.cache_hit ?? false,
          })
          store.addHistory({ question, sql: msg.sql, timestamp: new Date().toISOString() })
          return
        }

        if (msg.type === 'error') {
          store.setQueryError(msg.message ?? msg.error ?? 'Unknown error', msg.error_type)
          return
        }

        if (msg.type === 'token') {
          store.appendStreamingText(msg.content ?? '')
          return
        }
      } catch {
        // Not a JSON frame — treat as raw token chunk
        store.appendStreamingText(raw)
      }
    }

    ws.onerror = () => {
      store.setQueryError('WebSocket connection error')
    }

    ws.onclose = (e) => {
      wsRef.current = null
      if (e.code !== 1000 && store.query_status === 'streaming') {
        store.setQueryError('Connection closed unexpectedly')
      }
    }
  }, [close, store])

  const abort = useCallback(() => {
    close()
    store.setQueryStatus('idle')
    store.setStreamingText('')
  }, [close, store])

  return { connect, close, abort }
}