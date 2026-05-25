import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useStore } from './store/usestore'
import { Login } from './pages/login'
import { Register } from './pages/register'
import { Dashboard } from './pages/dashboard'
import { ToastContainer } from './components/toast'
import { LoadingOverlay } from './components/LoadingOverlay'

function RequireAuth({ children }: { children: JSX.Element }) {
  const { access_token } = useStore()
  if (!access_token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastContainer />
      <LoadingOverlay />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}