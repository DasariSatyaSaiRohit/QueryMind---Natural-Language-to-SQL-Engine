import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, AuthTokens } from '../types';
import { clearTokens, setTokens } from '../lib/api';

interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isLoggedIn: boolean;
  setAuth: (user: User, tokens: AuthTokens) => void;
  updateTokens: (tokens: AuthTokens) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      tokens: null,
      isLoggedIn: false,

      setAuth: (user, tokens) => {
        setTokens(tokens);
        set({ user, tokens, isLoggedIn: true });
      },

      updateTokens: (tokens) => {
        setTokens(tokens);
        set({ tokens });
      },

      logout: () => {
        clearTokens();
        set({ user: null, tokens: null, isLoggedIn: false });
      },
    }),
    {
      name: 'querymind_auth',
    }
  )
);
