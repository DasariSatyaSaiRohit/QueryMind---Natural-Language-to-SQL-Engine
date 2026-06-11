import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { QuerySession, QueryResult, QueryHistoryItem } from '../types';

interface QueryState {
  currentSession: QuerySession | null;
  currentResult: QueryResult | null;
  history: QueryHistoryItem[];
  isLoading: boolean;
  setSession: (session: QuerySession | null) => void;
  setResult: (result: QueryResult | null) => void;
  setHistory: (history: QueryHistoryItem[]) => void;
  addHistoryItem: (item: QueryHistoryItem) => void;
  removeHistoryItem: (id: string) => void;
  setLoading: (loading: boolean) => void;
  clearSession: () => void;
}

export const useQueryStore = create<QueryState>()(
  persist(
    (set) => ({
      currentSession: null,
      currentResult: null,
      history: [],
      isLoading: false,

      setSession: (session) => set({ currentSession: session }),
      setResult: (result) => set({ currentResult: result }),
      setHistory: (history) => set({ history }),
      addHistoryItem: (item) =>
        set((state) => ({ history: [item, ...state.history] })),
      removeHistoryItem: (id) =>
        set((state) => ({
          history: state.history.filter((h) => h.id !== id),
        })),
      setLoading: (loading) => set({ isLoading: loading }),
      clearSession: () =>
        set({ currentSession: null, currentResult: null, history: [] }),
    }),
    {
      name: 'querymind_query',
      partialize: (state) => ({ history: state.history }),
    }
  )
);
