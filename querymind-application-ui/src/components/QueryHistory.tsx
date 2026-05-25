import { useStore } from '../store/usestore'

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

export function QueryHistory() {
  const { history, setQuestion } = useStore()

  return (
    <div className="panel-section" style={{ flex: 1 }}>
      <div className="section-title">Recent Queries</div>
      {history.length === 0 ? (
        <div className="history-empty">No queries yet</div>
      ) : (
        <div className="history-list">
          {history.map((item, i) => (
            <div
              key={i}
              className="history-item"
              onClick={() => setQuestion(item.question)}
              title={item.question}
            >
              <div className="history-q">{item.question}</div>
              <div className="history-time">{formatTime(item.timestamp)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}