import { useStore } from '../store/usestore'

const icons = { success: '✓', error: '✕', info: 'ℹ' }

export function ToastContainer() {
  const { toasts, removeToast } = useStore()
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}${t.exiting ? ' exiting' : ''}`}>
          <span className="toast-icon">{icons[t.type]}</span>
          <div className="toast-body">
            <div className="toast-title">{t.title}</div>
            {t.message && <div className="toast-msg">{t.message}</div>}
          </div>
          <button className="toast-close" onClick={() => removeToast(t.id)}>×</button>
        </div>
      ))}
    </div>
  )
}