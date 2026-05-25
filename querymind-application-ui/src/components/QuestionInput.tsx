import { useStore } from '../store/usestore'
import { useWebSocket } from '../hooks/usewebsocket'
import { useQueryResults } from '../hooks/usequeryresults'
import { useEffect } from 'react'

export function QuestionInput() {
  const { question, setQuestion, session_id, session_status, access_token, query_status, sql } = useStore()
  const { connect, abort } = useWebSocket()
  const { fetchResults } = useQueryResults()

  const isStreaming = query_status === 'streaming'
  const isConnected = session_status === 'connected'

  const handleAsk = () => {
    if (!session_id || !access_token || !question.trim()) return
    connect(session_id, access_token, question.trim())
  }

  // Auto-fetch results when SQL is available after streaming completes
  useEffect(() => {
    if (query_status === 'complete' && sql) {
      fetchResults(1, 50, sql)
    }
  }, [query_status, sql]) // eslint-disable-line

  return (
    <div className="question-wrap">
      <textarea
        className="question-textarea"
        placeholder={isConnected ? 'Ask a question about your data...' : 'Connect a database first'}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        disabled={!isConnected || isStreaming}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAsk()
        }}
      />
      <div className="question-actions">
        <span className="ask-hint">
          {isConnected ? '⌘ + Enter to ask' : 'Connect a database to start'}
        </span>
        {isStreaming ? (
          <button className="btn-ask streaming" onClick={abort}>
            ■ Stop
          </button>
        ) : (
          <button
            className="btn-ask"
            onClick={handleAsk}
            disabled={!isConnected || !question.trim()}
          >
            ▶ Ask
          </button>
        )}
      </div>
    </div>
  )
}