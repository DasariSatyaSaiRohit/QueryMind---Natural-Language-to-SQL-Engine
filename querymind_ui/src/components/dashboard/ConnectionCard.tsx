import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, Table2, ChevronRight } from 'lucide-react';
import { DBConnection } from '../../types';

interface Props {
  connection: DBConnection;
  onDelete: (id: string) => void;
}

export default function ConnectionCard({ connection, onDelete }: Props) {
  const navigate = useNavigate();
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [hovered, setHovered] = useState(false);  
  const visibleTables = connection.table_names.length > 5 ? connection.table_names.slice(0, 5) : connection.table_names;
  const remainingCount = connection.table_names.length>5? connection.table_names.length - 5 : 0;

  const dbTypeColors: Record<string, string> = {
    postgresql: 'text-blue-400 bg-blue-400/10',
    mysql: 'text-orange-400 bg-orange-400/10',
    sqlite: 'text-purple-400 bg-purple-400/10',
  };
  const typeClass = dbTypeColors[connection.db_type] || 'text-slate-400 bg-slate-400/10';

  return (
    <>
      <div
        className="glass-card rounded-xl p-5 cursor-pointer group relative transition-all duration-200 hover:border-brand-500/40 hover:brand-glow"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => navigate(`/query/${connection.connection_id}`,{state:{connection}})}
      >
        {/* Tooltip */}
        {hovered && connection.table_names.length > 0 && (
          <div className="absolute bottom-full left-0 mb-2 z-10 w-64 bg-slate-800 border border-slate-700 rounded-lg p-3 shadow-xl animate-fade-in">
            <p className="text-xs text-slate-400 mb-2 font-medium">Tables</p>
            <div className="flex flex-wrap gap-1">
              {visibleTables.map(t => (
                <span key={t} className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">
                  {t}
                </span>
              ))}
              {remainingCount > 0 && (
                <span className="text-xs text-slate-500">+{remainingCount} more</span>
              )}
            </div>
          </div>
        )}

        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <h3 className="font-display font-semibold text-white text-lg mb-1 truncate">
              {connection.db_name}
            </h3>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${typeClass}`}>
              {connection.db_type}
            </span>
          </div>
          <button
            onClick={e => { e.stopPropagation(); setShowDeleteModal(true); }}
            className="btn-danger p-2 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <Trash2 size={15} />
          </button>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-slate-400">
            <Table2 size={14} />
            <span className="text-sm">{connection.table_count} tables</span>
          </div>
          <ChevronRight size={16} className="text-slate-600 group-hover:text-brand-400 transition-colors" />
        </div>

        {connection.last_accessed && (
          <p className="mt-2 text-xs text-slate-600">
            Last used {new Date(connection.last_accessed).toLocaleDateString()}
          </p>
        )}
      </div>

      {/* Delete confirmation modal */}
      {showDeleteModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in"
          onClick={() => setShowDeleteModal(false)}
        >
          <div
            className="glass-card rounded-xl w-full max-w-sm p-6 animate-slide-up"
            onClick={e => e.stopPropagation()}
          >
            <h4 className="font-display font-semibold text-white text-lg mb-2">Remove connection?</h4>
            <p className="text-slate-400 text-sm mb-6">
              <span className="text-white font-medium">{connection.db_name}</span> will be removed from your dashboard.
            </p>
            <div className="flex gap-3">
              <button
                className="btn-secondary flex-1"
                onClick={() => setShowDeleteModal(false)}
              >
                Cancel
              </button>
              <button
                className="bg-red-500/10 hover:bg-red-500/20 text-red-400 font-medium px-6 py-3 rounded-lg transition-all duration-200 flex-1 text-sm"
                onClick={() => { onDelete(connection.connection_id); setShowDeleteModal(false); }}
              >
                Remove
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
