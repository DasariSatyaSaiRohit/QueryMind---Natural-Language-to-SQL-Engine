import { useCallback, useState } from 'react'
import api from '../lib/axios'
import { useStore, ResultsObject } from '../store/usestore'

export function useQueryResults() {
  const { session_id, sql, setResults, addToast } = useStore()
  const [loading, setLoading] = useState(false)

  const fetchResults = useCallback(async (page = 1, pageSize = 50, overrideSql?: string) => {
    const activeSql = overrideSql ?? sql
    if (!session_id || !activeSql) return

    setLoading(true)
    try {
      const res = await api.post<ResultsObject>('/query/execute-only', {
        session_id,
        sql: activeSql,
        page,
        page_size: pageSize,
      })
      setResults(res.data)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? 'Failed to fetch results'
      addToast({ type: 'error', title: 'Execution Error', message: msg })
    } finally {
      setLoading(false)
    }
  }, [session_id, sql, setResults, addToast])

  return { fetchResults, loading }
}