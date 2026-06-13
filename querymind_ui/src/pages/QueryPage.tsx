import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom';
import { ArrowLeft, Database, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../lib/api';
import { useQueryStore } from '../stores/queryStore';
import { QueryResult, QueryHistoryItem, QuerySession, HistoryItem } from '../types';
import QueryInput from '../components/query/QueryInput';
import ResultsPanel from '../components/query/ResultsPanel';
import HistoryPanel from '../components/query/HistoryPanel';

export default function QueryPage() {
  const location = useLocation();
  const stateData = location.state;
  const { connectionId } = useParams<{ connectionId: string }>();
  const navigate = useNavigate();
  const {
    currentSession,
    setSession,
    currentResult,
    setResult,
    history,
    setHistory,
    addHistoryItem,
    removeHistoryItem,
    isLoading,
    setLoading,
    clearSession,
  } = useQueryStore();

  const [question, setQuestion] = useState('');
  // const [connectionName, setConnectionName] = useState();
  const [sessionLoading, setSessionLoading] = useState(false);

  useEffect(() => {
    if (connectionId) {
      initSession(connectionId);
    }
  }, [connectionId]);

  const initSession = async (connId: string) => {
    setSessionLoading(true);
    try {
      const sessionRes: any = await api.post<any>('/session/connect', {
        connection_id: connId,
      });
      setSession(sessionRes.data.data);
      await getHistory();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Failed to connect to database';
      toast.error(msg);
      navigate('/dashboard');
    } finally {
      setSessionLoading(false);
    }
  };

  const getHistory = async () => {
    const historyRes = await api.get<any>(`/query/history/${currentSession?.session_id}`);
    setHistory(historyRes.data.data);
  };

  const handleSubmit = async () => {
    if (!question.trim() || !currentSession) return;
    setLoading(true);
    try {
      const response = await api.post<any>('/query/ask', {
        session_id: currentSession.session_id,
        type: stateData.db_type,
        question: question.trim(),
      });

      const result = response.data;
      if (result.success === false) {
        toast.error(result.message || 'Query failed. Please try again.');
        return;
      }
      setResult(result.data);

      // Add to history
      const historyItem: QueryHistoryItem = {
        id: crypto.randomUUID(),
        session_id: currentSession.session_id,
        user_input: question.trim(),
        sql_query: result.sql,
        status: 'success',
        created_at: new Date().toISOString(),
        is_deleted: false,
      };

      addHistoryItem(historyItem);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Query failed. Please try again.';
      toast.error(msg);

      // Add failed entry to history
      if (currentSession) {
        const failedItem: QueryHistoryItem = {
          id: crypto.randomUUID(),
          session_id: currentSession.session_id,
          user_input: question.trim(),
          sql_query: '',
          status: 'error',
          created_at: new Date().toISOString(),
          is_deleted: false,
        };
        addHistoryItem(failedItem);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRerun = async (sql: string) => {
    if (!currentSession) return;
    setLoading(true);
    try {
      const response = await api.post<QueryResult>('/query/execute', {
        session_id: currentSession.session_id,
        sql,
      });
      setResult(response.data);
      toast.success('Query re-executed');
    } catch (error) {
      toast.error('Re-execution failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteHistory = async (id: string) => {
    try {
      await api.delete(`/query/history/${id}`);
      removeHistoryItem(id);
    } catch (error) {
      removeHistoryItem(id); // Optimistic delete
    }
  };

  if (sessionLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-400">
          <Loader2 size={20} className="animate-spin" />
          <span>Connecting to database...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col">
      {/* Top nav */}
      <nav className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="px-6 h-14 flex items-center gap-4">
          <Link to="/dashboard" className="btn-ghost flex items-center gap-2 py-2">
            <ArrowLeft size={15} />
            <span className="hidden sm:inline text-sm">Dashboard</span>
          </Link>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-2">
            <Database size={14} className="text-brand-400" />
            <span className="text-sm text-slate-300 font-medium">
              {stateData?.connection?.db_name || connectionId}
            </span>
          </div>
        </div>
      </nav>

      {/* Three-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Query Input (30%) */}
        <aside className="w-[30%] min-w-[240px] border-r border-slate-800 p-5 flex flex-col">
          <QueryInput
            question={question}
            setQuestion={setQuestion}
            onSubmit={handleSubmit}
            loading={isLoading}
          />
        </aside>

        {/* Center: Results (50%) */}
        <main className="flex-1 p-5 overflow-y-auto">
          <div className="mb-4">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-widest">
              Results
            </span>
          </div>
          <ResultsPanel result={currentResult} />
        </main>

        {/* Right: History (20%) */}
        <aside className="w-[20%] min-w-[180px] border-l border-slate-800 p-4 overflow-hidden flex flex-col">
          <>
            <HistoryPanel history={history} onRerun={handleRerun} onDelete={handleDeleteHistory} />
          </>
        </aside>
      </div>
    </div>
  );
}
