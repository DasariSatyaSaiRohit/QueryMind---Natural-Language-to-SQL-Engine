import { useState } from 'react';
import { ChevronDown, ChevronUp, Trash2, RotateCcw, CheckCircle2, XCircle, History } from 'lucide-react';
import { QueryHistoryItem } from '../../types';

interface Props {
  history: QueryHistoryItem[];
  onRerun: (sql: string) => void;
  onDelete: (id: string) => void;
}

function HistoryItem({
  item,
  onRerun,
  onDelete,
}: {
  item: QueryHistoryItem;
  onRerun: (sql: string) => void;
  onDelete: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const title = item.question.length > 50 ? item.question.slice(0, 50) + '…' : item.question;

  return (
    <div className="glass-card rounded-lg overflow-hidden">
      <div
        className="flex items-start gap-3 p-3 cursor-pointer hover:bg-slate-700/20 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-shrink-0 mt-0.5">
          {item.status === 'success' ? (
            <CheckCircle2 size={14} className="text-brand-400" />
          ) : (
            <XCircle size={14} className="text-red-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 leading-snug">{title}</p>
          <p className="text-xs text-slate-600 mt-1">
            {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
        </div>
        {expanded ? <ChevronUp size={14} className="text-slate-600 flex-shrink-0 mt-0.5" /> : <ChevronDown size={14} className="text-slate-600 flex-shrink-0 mt-0.5" />}
      </div>

      {expanded && (
        <div className="border-t border-slate-700/50 p-3 space-y-3">
          <div>
            <p className="text-xs text-slate-500 mb-1">Question</p>
            <p className="text-xs text-slate-300 leading-relaxed">{item.question}</p>
          </div>
          {item.sql && (
            <div>
              <p className="text-xs text-slate-500 mb-1">SQL</p>
              <pre className="text-xs text-slate-400 font-mono bg-slate-900 rounded-lg p-2 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {item.sql}
              </pre>
            </div>
          )}
          <div className="flex gap-2">
            <button
              onClick={e => { e.stopPropagation(); onRerun(item.sql); }}
              className="btn-secondary flex items-center gap-1.5 py-1.5 flex-1 justify-center text-xs"
            >
              <RotateCcw size={12} /> Re-run
            </button>
            {!showConfirm ? (
              <button
                onClick={e => { e.stopPropagation(); setShowConfirm(true); }}
                className="btn-danger flex items-center gap-1.5 py-1.5 flex-1 justify-center text-xs"
              >
                <Trash2 size={12} /> Delete
              </button>
            ) : (
              <button
                onClick={e => { e.stopPropagation(); onDelete(item.id); }}
                className="bg-red-500/20 text-red-400 flex items-center gap-1.5 py-1.5 flex-1 justify-center text-xs rounded-lg hover:bg-red-500/30 transition-colors"
              >
                Confirm
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function HistoryPanel({ history, onRerun, onDelete }: any) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-4">
        <History size={14} className="text-slate-400" />
        <span className="text-xs font-medium text-slate-400 uppercase tracking-widest">History</span>
      </div>

      {history.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center py-8">
          <p className="text-slate-600 text-xs">No queries yet</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto space-y-2 max-h-[calc(100vh-200px)]">
          {history.map((item:any) => (
            <HistoryItem key={item.id} item={item} onRerun={onRerun} onDelete={onDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
