import { useNavigate } from 'react-router-dom'
import { useStore } from '../store/usestore'
import { ConnectionPanel } from '../components/ConnectionPanel'
import { QueryHistory } from '../components/QueryHistory'
import { QuestionInput } from '../components/QuestionInput'
import { StreamingPanel } from '../components/streamingpanel'
import { ResultsTable } from '../components/resultsTable'

export function Dashboard() {
  const { user, clearAuth, clearSession } = useStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    clearAuth()
    clearSession()
    navigate('/login')
  }

  return (
    <div className="dashboard">
      {/* Top Bar */}
      <header className="topbar">
        <div className="topbar-logo">
          <div className="topbar-logo-icon">◈</div>
          QueryMind
        </div>
        <div className="topbar-right">
          {user && <span className="topbar-user">{user.email}</span>}
          <button className="btn-ghost" onClick={handleLogout}>Sign out</button>
        </div>
      </header>

      {/* Left Sidebar */}
      <aside className="sidebar">
        <ConnectionPanel />
        <QueryHistory />
      </aside>

      {/* Center Panel */}
      <main className="center-panel">
        <QuestionInput />
        <StreamingPanel />
      </main>

      {/* Right Panel */}
      <aside className="right-panel">
        <div className="panel-section" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="section-title">Results</div>
        </div>
        <ResultsTable />
      </aside>
    </div>
  )
}