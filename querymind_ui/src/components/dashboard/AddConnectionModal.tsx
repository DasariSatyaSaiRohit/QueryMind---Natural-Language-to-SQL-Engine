import { useState } from 'react';
import { X, Database, Loader2, CheckCircle2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../lib/api';
import { DBConnection } from '../../types';

interface Props {
  onClose: () => void;
  onAdded: (connection: DBConnection) => void;
}

const DB_PATTERNS = {
  postgresql: /^(postgresql|postgres):\/\//i,
  mysql: /^mysql:\/\//i,
  sqlite: /^(sqlite:\/\/\/|sqlite:\/\/)/i,
};

function extractDbName(url: string): string {
  try {
    const match = url.match(/\/([^/?#]+)(\?|#|$)/);
    if (match) return match[1];
    const fileMatch = url.match(/\/([^/]+\.db)(\?|$)/i);
    if (fileMatch) return fileMatch[1];
  } catch {
    // ignore
  }
  return 'unknown';
}

function detectDbType(url: string): string | null {
  for (const [type, pattern] of Object.entries(DB_PATTERNS)) {
    if (pattern.test(url)) return type;
  }
  return null;
}

export default function AddConnectionModal({ onClose, onAdded }: Props) {
  const [url, setUrl] = useState('');
  const [tested, setTested] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);

  const dbType = detectDbType(url);
  const dbName = url ? extractDbName(url) : '';
  const urlValid = url.trim().length > 0 && dbType !== null;

  const handleTest = async () => {
    if (!urlValid) {
      toast.error('Please enter a valid connection URL');
      return;
    }
    setTesting(true);
    setTested(false);
    try {
      await api.post('/connections/test_connection', { url });
      setTested(true);
      toast.success('Connection successful!');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Connection failed. Check your URL.';
      toast.error(msg);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!tested) return;
    setSaving(true);
    try {
      const response = await api.post<DBConnection>('/connections/add', { url });
      onAdded(response.data);
      toast.success('Database connected!');
      onClose();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Failed to save connection';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className="glass-card rounded-2xl w-full max-w-lg animate-slide-up">
        <div className="flex items-center justify-between p-6 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-brand-500/10 rounded-lg flex items-center justify-center">
              <Database size={18} className="text-brand-400" />
            </div>
            <h3 className="font-display font-semibold text-white text-lg">Add Database Connection</h3>
          </div>
          <button onClick={onClose} className="btn-ghost p-2">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Connection URL</label>
            <input
              type="text"
              value={url}
              onChange={e => { setUrl(e.target.value); setTested(false); }}
              className="input-field font-mono text-xs"
              placeholder="postgresql://user:pass@host:5432/dbname"
            />
            <p className="mt-1.5 text-xs text-slate-500">
              Supports: postgresql://, mysql://, sqlite:///
            </p>
          </div>

          {url && (
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-900 rounded-lg p-3">
                <p className="text-xs text-slate-500 mb-1">Database Name</p>
                <p className="text-sm text-slate-200 font-medium truncate">{dbName || '—'}</p>
              </div>
              <div className="bg-slate-900 rounded-lg p-3">
                <p className="text-xs text-slate-500 mb-1">Type</p>
                <p className={`text-sm font-medium capitalize ${dbType ? 'text-brand-400' : 'text-red-400'}`}>
                  {dbType || 'Unsupported'}
                </p>
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleTest}
              disabled={testing || !urlValid}
              className="btn-secondary flex items-center gap-2 flex-1"
            >
              {testing ? (
                <><Loader2 size={16} className="animate-spin" /> Testing...</>
              ) : tested ? (
                <><CheckCircle2 size={16} className="text-brand-400" /> Connected</>
              ) : (
                'Test Connection'
              )}
            </button>
            <button
              onClick={handleSave}
              disabled={!tested || saving}
              className="btn-primary flex items-center gap-2 flex-1"
            >
              {saving ? (
                <><Loader2 size={16} className="animate-spin" /> Saving...</>
              ) : (
                'Save Connection'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
