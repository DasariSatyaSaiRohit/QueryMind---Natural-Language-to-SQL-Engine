import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useEffect } from 'react';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import QueryPage from './pages/QueryPage';
import { useAuthStore } from './stores/authStore';
import { getTokens, isTokenExpiredOrExpiringSoon, setTokens, clearTokens } from './lib/api';
import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  
  const { isLoggedIn } = useAuthStore();
  if (!isLoggedIn) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isLoggedIn } = useAuthStore();
  if (isLoggedIn) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
}

function AppInit() {
  const { updateTokens, logout } = useAuthStore();

  useEffect(() => {
    const initTokenRefresh = async () => {
      const tokens = getTokens();
      if (!tokens) return;
      if (isTokenExpiredOrExpiringSoon(tokens)) {
        try {
          const response = await axios.post(`${BASE_URL}/auth/refresh`, {
            refresh_token: tokens.refresh_token,
          });
          const newTokens = response.data.data;
          setTokens(newTokens);
          updateTokens(newTokens);
        } catch {
          clearTokens();
          logout();
        }
      }
    };
    initTokenRefresh();
  }, [updateTokens, logout]);

  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <AppInit />
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#1e293b',
            color: '#e2e8f0',
            border: '1px solid #334155',
            fontFamily: 'DM Sans, sans-serif',
            fontSize: '14px',
          },
          success: {
            iconTheme: { primary: '#17b06a', secondary: '#0f172a' },
          },
          error: {
            iconTheme: { primary: '#ef4444', secondary: '#0f172a' },
          },
        }}
      />
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route
          path="/login"
          element={<PublicRoute><LoginPage /></PublicRoute>}
        />
        <Route
          path="/register"
          element={<PublicRoute><RegisterPage /></PublicRoute>}
        />
        <Route
          path="/dashboard"
          element={<ProtectedRoute><DashboardPage /></ProtectedRoute>}
        />
        <Route
          path="/query/:connectionId"
          element={<ProtectedRoute><QueryPage /></ProtectedRoute>}
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
