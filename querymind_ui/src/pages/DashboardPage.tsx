import { useState, useEffect } from 'react';
import { Plus, Database, LogOut, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../lib/api';
import { useAuthStore } from '../stores/authStore';
import { DBConnection } from '../types';
import ConnectionCard from '../components/dashboard/ConnectionCard';
import AddConnectionModal from '../components/dashboard/AddConnectionModal';

function SkeletonCard() {
  return (
    <div className="glass-card rounded-xl p-5 animate-pulse">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="h-5 w-32 bg-slate-700 rounded mb-2" />
          <div className="h-4 w-20 bg-slate-800 rounded-full" />
        </div>
      </div>
      <div className="h-4 w-24 bg-slate-800 rounded" />
    </div>
  );
}

export default function DashboardPage() {
  const { user, logout } = useAuthStore();
  const [connections, setConnections] = useState<DBConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    fetchConnections();    
  }, []);

  const fetchConnections = async () => {
    try {
      const response:any = await api.get<any[]>('/connections/list');      
      const sorted = [...response.data.data.connections].sort((a, b) => {
        if (!a.last_accessed) return 1;
        if (!b.last_accessed) return -1;
        return new Date(b.last_accessed).getTime() - new Date(a.last_accessed).getTime();
      });
      setConnections(sorted);
    } catch {
      toast.error('Failed to load connections');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/connections/${id}`);
      setConnections(prev => prev.filter(c => c.connection_id !== id));
      toast.success('Connection removed');
    } catch {
      toast.error('Failed to remove connection');
    }
  };

  const handleAdded = (connection: DBConnection) => {    
    setConnections(prev => [connection, ...prev]);
  };

  return (
    <div className="min-h-screen bg-slate-950">
      {/* Navbar */}
      <nav className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
              <Database size={16} className="text-white" />
            </div>
            <span className="font-display font-bold text-white tracking-tight">QueryMind</span>
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-400">{user?.email}</span>
            <button
              onClick={logout}
              className="btn-ghost flex items-center gap-2"
            >
              <LogOut size={15} />
              <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-display text-3xl font-bold text-white mb-1">Your Databases</h1>
            <p className="text-slate-400 text-sm">
              {loading ? '' : `${connections.length} connection${connections.length !== 1 ? 's' : ''}`}
            </p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus size={16} />
            Add New DB
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => <SkeletonCard key={i} />)}
          </div>
        ) : connections.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 bg-slate-800 rounded-2xl flex items-center justify-center mb-4">
              <Database size={28} className="text-slate-600" />
            </div>
            <h3 className="font-display text-xl font-semibold text-white mb-2">No databases yet</h3>
            <p className="text-slate-400 text-sm mb-6 max-w-sm">
              Connect your first database to start querying with natural language.
            </p>
            <button
              onClick={() => setShowAddModal(true)}
              className="btn-primary flex items-center gap-2"
            >
              <Plus size={16} />
              Add Your First DB
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 animate-fade-in">
            {connections.map(conn => (
              <ConnectionCard
                key={conn.connection_id}
                connection={conn}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </main>

      {showAddModal && (
        <AddConnectionModal
          onClose={() => setShowAddModal(false)}
          onAdded={handleAdded}
        />
      )}
    </div>
  );
}
