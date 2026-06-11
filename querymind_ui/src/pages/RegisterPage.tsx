import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Eye, EyeOff, Database, CheckCircle2, XCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import api, { setTokens } from '../lib/api';
import { useAuthStore } from '../stores/authStore';
import { AuthTokens, User } from '../types';

const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

interface PasswordStrength {
  minLength: boolean;
  hasUppercase: boolean;
  hasNumber: boolean;
  hasSpecial: boolean;
}

function checkPasswordStrength(password: string): PasswordStrength {
  return {
    minLength: password.length >= 8,
    hasUppercase: /[A-Z]/.test(password),
    hasNumber: /[0-9]/.test(password),
    hasSpecial: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password),
  };
}

function StrengthItem({ met, label }: { met: boolean; label: string }) {
  return (
    <div className={`flex items-center gap-2 text-xs transition-colors ${met ? 'text-brand-400' : 'text-slate-500'}`}>
      {met ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
      {label}
    </div>
  );
}

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const { setAuth } = useAuthStore();

  const strength = checkPasswordStrength(password);
  const allMet = Object.values(strength).every(Boolean);
  const emailValid = EMAIL_REGEX.test(email);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailValid) {
      toast.error('Please enter a valid email address');
      return;
    }
    if (!allMet) {
      toast.error('Password does not meet requirements');
      return;
    }
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post<{ user: User; tokens: AuthTokens }>('/auth/register', {
        email,
        password,
      });
      const { user, tokens } = response.data;
      setTokens(tokens);
      setAuth(user, tokens);
      toast.success('Account created! Welcome to QueryMind.');
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Registration failed. Please try again.';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-8">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-9 h-9 bg-brand-500 rounded-lg flex items-center justify-center">
            <Database size={18} className="text-white" />
          </div>
          <span className="font-display font-700 text-xl text-white tracking-tight">QueryMind</span>
        </div>

        <div className="mb-8 animate-fade-in">
          <h2 className="font-display text-3xl font-bold text-white mb-2">Create account</h2>
          <p className="text-slate-400">Start querying your databases in plain English.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5 animate-slide-up">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className={`input-field ${email && !emailValid ? 'border-red-500 focus:ring-red-500' : ''}`}
              placeholder="you@company.com"
            />
            {email && !emailValid && (
              <p className="mt-1.5 text-xs text-red-400">Please enter a valid email address</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input-field pr-12"
                placeholder="Create a strong password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {password && (
              <div className="mt-3 grid grid-cols-2 gap-1.5">
                <StrengthItem met={strength.minLength} label="8+ characters" />
                <StrengthItem met={strength.hasUppercase} label="Uppercase letter" />
                <StrengthItem met={strength.hasNumber} label="Number" />
                <StrengthItem met={strength.hasSpecial} label="Special character" />
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Confirm Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className={`input-field ${confirmPassword && password !== confirmPassword ? 'border-red-500 focus:ring-red-500' : ''}`}
              placeholder="Repeat your password"
            />
            {confirmPassword && password !== confirmPassword && (
              <p className="mt-1.5 text-xs text-red-400">Passwords don't match</p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading || !allMet || !emailValid || password !== confirmPassword}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating account...
              </>
            ) : (
              'Create account'
            )}
          </button>
        </form>

        <p className="mt-6 text-center text-slate-400 text-sm">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
