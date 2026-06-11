import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Eye, EyeOff, Database, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import api, { setTokens } from '../lib/api';
import { useAuthStore } from '../stores/authStore';
import { AuthTokens, User } from '../types';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('Please fill in all fields');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post<any>('/auth/login', {
        email,
        password,
      });
      const { user, tokens } = response.data.data;
      
      setTokens(tokens);
      setAuth(user, tokens);
      toast.success('Welcome back!');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Invalid credentials';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex">
      {/* Left branding panel */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 bg-slate-900 p-12 border-r border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-brand-500 rounded-lg flex items-center justify-center">
            <Database size={18} className="text-white" />
          </div>
          <span className="font-display font-700 text-xl text-white tracking-tight">QueryMind</span>
        </div>
        <div>
          <div className="flex items-center gap-2 mb-6">
            <Zap size={16} className="text-brand-400" />
            <span className="text-brand-400 text-sm font-medium uppercase tracking-widest">Natural Language SQL</span>
          </div>
          <h1 className="font-display text-5xl font-bold text-white leading-tight mb-6">
            Ask questions.<br />
            Get answers.
          </h1>
          <p className="text-slate-400 text-lg leading-relaxed max-w-sm">
            Connect your databases and query them in plain English. No SQL expertise required.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-4">
          {['PostgreSQL', 'MySQL', 'SQLite'].map(db => (
            <div key={db} className="bg-slate-800 rounded-lg p-3 text-center border border-slate-700">
              <span className="text-slate-300 text-sm font-medium">{db}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right form panel */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-10">
            <div className="w-9 h-9 bg-brand-500 rounded-lg flex items-center justify-center">
              <Database size={18} className="text-white" />
            </div>
            <span className="font-display font-700 text-xl text-white tracking-tight">QueryMind</span>
          </div>

          <div className="mb-8 animate-fade-in">
            <h2 className="font-display text-3xl font-bold text-white mb-2">Sign in</h2>
            <p className="text-slate-400">Welcome back — let's get querying.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5 animate-slide-up">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="input-field"
                placeholder="you@company.com"
                autoComplete="email"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="input-field pr-12"
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </>
              ) : (
                'Sign in'
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-slate-400 text-sm">
            Don't have an account?{' '}
            <Link to="/register" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
