import { useState } from 'react';
import { ChevronDown, ChevronUp, Copy, Check, Clock, Hash } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import toast from 'react-hot-toast';
import { QueryResult } from '../../types';

const PAGE_SIZE = 50;

interface Props {
  result: QueryResult | null;
}

export default function ResultsPanel({ result }: Props) {  
  const [cotExpanded, setCotExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [page, setPage] = useState(0);

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center py-16">
        <div className="w-12 h-12 bg-slate-800 rounded-xl flex items-center justify-center mb-3">
          <Hash size={22} className="text-slate-600" />
        </div>
        <p className="text-slate-500 text-sm">Results will appear here</p>
      </div>
    );
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(result.sql);
    setCopied(true);
    toast.success('SQL copied!');
    setTimeout(() => setCopied(false), 2000);
  };

  const totalPages = Math.ceil(result.rows.length / PAGE_SIZE);
  const pageRows = result.rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  

  return (
    <div className="flex flex-col gap-5 h-full overflow-y-auto">
      {/* Chain of Thought */}
      {result.chain_of_thought.length > 0 && (
        <div className="glass-card rounded-xl overflow-hidden">
          <button
            onClick={() => setCotExpanded(!cotExpanded)}
            className="w-full flex items-center justify-between p-4 hover:bg-slate-700/20 transition-colors"
          >
            <span className="text-sm font-medium text-slate-300">Chain of Thought</span>
            {cotExpanded ? <ChevronUp size={16} className="text-slate-500" /> : <ChevronDown size={16} className="text-slate-500" />}
          </button>
          {cotExpanded && (
            <div className="px-4 pb-4 border-t border-slate-700/50">
              <ol className="space-y-2 mt-3">
                {result.chain_of_thought.map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="flex-shrink-0 w-5 h-5 bg-brand-500/10 text-brand-400 rounded-full flex items-center justify-center text-xs font-mono font-medium">
                      {i + 1}
                    </span>
                    <span className="text-slate-400 leading-relaxed">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      {/* SQL Query */}
      <div className="glass-card rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
          <span className="text-sm font-medium text-slate-300">Generated SQL</span>
          <button onClick={handleCopy} className="btn-ghost flex items-center gap-1.5 py-1.5">
            {copied ? <><Check size={14} className="text-brand-400" /> Copied!</> : <><Copy size={14} /> Copy</>}
          </button>
        </div>
        <SyntaxHighlighter
          language="sql"
          style={vscDarkPlus}
          customStyle={{
            margin: 0,
            padding: '1rem',
            background: 'transparent',
            fontSize: '13px',
            lineHeight: '1.6',
          }}
        >
          {result.sql}
        </SyntaxHighlighter>
      </div>

      {/* Stats */}
      <div className="flex gap-3">
        <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-800/50 rounded-lg px-3 py-2">
          <Hash size={13} />
          {result.row_count.toLocaleString()} rows
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500 bg-slate-800/50 rounded-lg px-3 py-2">
          <Clock size={13} />
          {result.execution_time_ms}ms
        </div>
      </div>

      {/* Results Table */}
      {result.rows.length > 0 && (
        <div className="glass-card rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700/50">
                  {result.columns.map(col => (
                    <th key={col} className="text-left px-4 py-3 text-xs font-medium text-slate-400 uppercase tracking-wider whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row, i) => (
                  <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                    {result.columns.map((col,j) => (
                      <td key={col} className="px-4 py-3 text-slate-300 whitespace-nowrap max-w-[200px] truncate font-mono text-xs">
                        {row[col] === null ? (
                          <span className="text-slate-600 italic">null</span>
                        ) : String(row[j])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-700/50">
              <span className="text-xs text-slate-500">
                Page {page + 1} of {totalPages} ({result.rows.length} total rows)
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="btn-ghost py-1.5 px-3 text-xs disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                  disabled={page === totalPages - 1}
                  className="btn-ghost py-1.5 px-3 text-xs disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {result.rows.length === 0 && (
        <div className="glass-card rounded-xl p-6 text-center">
          <p className="text-slate-400 text-sm">Query executed successfully — no rows returned.</p>
        </div>
      )}
    </div>
  );
}
