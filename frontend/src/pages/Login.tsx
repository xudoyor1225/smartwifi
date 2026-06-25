import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wifi, Lock, User, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { useTheme } from '../context/ThemeContext';
import { LANGUAGES } from '../i18n';
import type { Language } from '../i18n';
import { Sun, Moon } from 'lucide-react';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const { t, language, setLanguage } = useLanguage();
  const { isDark, toggleTheme } = useTheme();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username.trim() || !password.trim()) {
      setError(t.login_fill_all);
      return;
    }
    setIsLoading(true);
    try {
      await login(username, password);
      navigate('/');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string }; status?: number } };
        if (axiosErr.response?.status === 429) {
          setError(t.login_too_many);
        } else if (axiosErr.response?.status === 401) {
          setError(t.login_wrong_credentials);
        } else {
          setError(axiosErr.response?.data?.detail || t.login_auth_error);
        }
      } else {
        setError(t.login_no_server);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-bg-primary flex items-center justify-center px-4 relative overflow-hidden">
      {/* Background gradient */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-brand-primary/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-brand-secondary/20 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 w-96 h-96 bg-brand-tertiary/10 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2" />
      </div>

      {/* Top right: language + theme */}
      <div className="absolute top-6 right-6 flex items-center gap-3 z-50">
        {/* Fancy Language Dropdown */}
        <div className="relative group">
          <button
            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-bg-secondary/50 backdrop-blur-xl border border-white/10 hover:border-brand-primary/50 text-fg-primary transition-all duration-300 shadow-[0_4px_30px_rgba(0,0,0,0.1)] hover:shadow-[0_0_20px_rgba(59,130,246,0.3)]"
          >
            <span className="text-xl leading-none drop-shadow-md">
              {LANGUAGES.find(l => l.code === language)?.flag}
            </span>
            <span className="text-sm font-semibold tracking-wide hidden sm:block">
              {LANGUAGES.find(l => l.code === language)?.code.toUpperCase()}
            </span>
          </button>
          
          <div className="absolute right-0 top-full mt-2 w-48 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-300 transform origin-top-right scale-95 group-hover:scale-100">
            <div className="p-2 rounded-2xl bg-bg-secondary/80 backdrop-blur-2xl border border-white/10 shadow-2xl flex flex-col gap-1">
              {LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  onClick={() => setLanguage(lang.code as Language)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all duration-200
                    ${lang.code === language
                      ? 'bg-brand-primary/20 text-brand-primary border border-brand-primary/30 shadow-[inset_0_0_10px_rgba(59,130,246,0.2)]'
                      : 'text-fg-secondary hover:bg-white/5 hover:text-fg-primary'
                    }`}
                >
                  <span className="text-xl leading-none drop-shadow-sm">{lang.flag}</span>
                  <div className="flex flex-col">
                    <span className="text-sm font-bold">{lang.nativeName}</span>
                    <span className="text-[10px] text-fg-muted uppercase tracking-wider">{lang.label}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="p-2.5 rounded-xl bg-bg-secondary/50 backdrop-blur-xl border border-white/10 hover:border-brand-primary/50 text-fg-muted hover:text-fg-primary transition-all duration-300 shadow-[0_4px_30px_rgba(0,0,0,0.1)] hover:shadow-[0_0_20px_rgba(59,130,246,0.3)]"
          aria-label="Toggle theme"
        >
          {isDark ? <Sun className="w-5 h-5 text-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.5)]" /> : <Moon className="w-5 h-5 text-indigo-400 drop-shadow-[0_0_8px_rgba(99,102,241,0.5)]" />}
        </button>
      </div>

      <div className="w-full max-w-md relative animate-fade-in">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-primary to-brand-secondary flex items-center justify-center shadow-glow-blue mb-4">
            <Wifi className="w-9 h-9 text-white" strokeWidth={2} />
          </div>
          <h1 className="text-3xl font-bold text-fg-primary">
            <span className="text-gradient-brand">Smart</span>WiFi
          </h1>
          <p className="text-sm text-fg-muted mt-1">Network Management Platform</p>
        </div>

        {/* Card */}
        <div className="card glass shadow-card-hover">
          <div className="mb-6">
            <h2 className="text-xl font-semibold text-fg-primary">{t.login_title}</h2>
            <p className="text-sm text-fg-muted mt-1">{t.login_subtitle}</p>
          </div>

          {sessionExpired && (
            <div className="mb-4 p-3 rounded-lg bg-status-warningBg border border-status-warning/30 flex items-start gap-2.5 animate-slide-up">
              <AlertCircle className="w-4 h-4 text-status-warning flex-shrink-0 mt-0.5" />
              <p className="text-sm text-status-warning">{t.login_session_expired}</p>
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 rounded-lg bg-status-dangerBg border border-status-danger/30 flex items-start gap-2.5 animate-slide-up">
              <AlertCircle className="w-4 h-4 text-status-danger flex-shrink-0 mt-0.5" />
              <p className="text-sm text-status-danger">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">
                {t.login_username}
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-muted pointer-events-none" />
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="input-field pl-10"
                  placeholder="admin"
                  autoComplete="username"
                  disabled={isLoading}
                  autoFocus
                />
              </div>
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">
                {t.login_password}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-muted pointer-events-none" />
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field pl-10"
                  placeholder="••••••••"
                  autoComplete="current-password"
                  disabled={isLoading}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full justify-center flex items-center gap-2 mt-6"
            >
              {isLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" />{t.login_submitting}</>
              ) : t.login_submit}
            </button>
          </form>
        </div>

        <p className="text-center text-2xs text-fg-subtle mt-6">{t.login_footer}</p>
      </div>
    </div>
  );
}
