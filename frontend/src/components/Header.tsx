import { useState, useRef, useEffect } from 'react';
import { Bell, LogOut, Router as RouterIcon, Sun, Moon, ChevronDown } from 'lucide-react';
import type { ConnectionStatus } from '../types';
import { useLanguage } from '../context/LanguageContext';
import { useTheme } from '../context/ThemeContext';

interface HeaderProps {
  adminName: string;
  connectionStatus: ConnectionStatus;
  unreadCount: number;
  onLogout: () => void;
}

function ConnectionIndicator({ status }: { status: ConnectionStatus }) {
  const { t } = useLanguage();
  const config = {
    connected:    { dotClass: 'status-dot-success', label: t.header_router_connected,    textColor: 'text-status-success' },
    disconnected: { dotClass: 'status-dot-danger',  label: t.header_router_disconnected, textColor: 'text-status-danger'  },
    connecting:   { dotClass: 'status-dot-warning', label: t.header_router_connecting,   textColor: 'text-status-warning' },
  };
  const { dotClass, label, textColor } = config[status];
  return (
    <div className="flex items-center gap-2.5 px-3 py-1.5 bg-bg-tertiary rounded-lg border border-border-subtle">
      <RouterIcon className="w-4 h-4 text-fg-muted" />
      <span className={dotClass} />
      <span className={`text-xs font-medium ${textColor}`}>{label}</span>
    </div>
  );
}

function LanguageSwitcher() {
  const { language, setLanguage, languages } = useLanguage();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const current = languages.find((l) => l.code === language)!;

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-gradient-to-br from-bg-secondary to-bg-tertiary border border-border-default hover:border-brand-primary/50 text-fg-primary transition-all duration-300 shadow-sm hover:shadow-[0_0_15px_rgba(59,130,246,0.15)] group"
        aria-label="Change language"
      >
        <span className="text-lg leading-none drop-shadow-sm group-hover:scale-110 transition-transform duration-300">{current.flag}</span>
        <span className="text-xs font-bold hidden sm:block uppercase tracking-wider">{current.code}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-fg-muted group-hover:text-brand-primary transition-all duration-300 ${open ? 'rotate-180 text-brand-primary' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-3 w-48 bg-bg-secondary/90 backdrop-blur-xl border border-border-default rounded-2xl shadow-2xl z-50 overflow-hidden animate-fade-in p-1.5">
          {languages.map((lang) => (
            <button
              key={lang.code}
              onClick={() => { setLanguage(lang.code); setOpen(false); }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all duration-200
                ${lang.code === language
                  ? 'bg-brand-primary/15 text-brand-primary border border-brand-primary/20'
                  : 'text-fg-secondary hover:bg-white/5 hover:text-fg-primary'
                }`}
            >
              <span className="text-xl leading-none drop-shadow-sm">{lang.flag}</span>
              <div className="flex flex-col">
                <span className="text-xs font-bold">{lang.nativeName}</span>
                <span className="text-[10px] uppercase tracking-wider opacity-70">{lang.label}</span>
              </div>
              {lang.code === language && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-brand-primary shadow-glow-blue" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ThemeToggle() {
  const { isDark, toggleTheme } = useTheme();
  return (
    <button
      onClick={toggleTheme}
      className="btn-icon"
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={isDark ? 'Light mode' : 'Dark mode'}
    >
      {isDark ? (
        <Sun className="w-4 h-4 text-status-warning" strokeWidth={2} />
      ) : (
        <Moon className="w-4 h-4 text-brand-secondary" strokeWidth={2} />
      )}
    </button>
  );
}

export default function Header({ adminName, connectionStatus, unreadCount, onLogout }: HeaderProps) {
  const { t } = useLanguage();

  return (
    <header className="fixed top-0 left-60 right-0 h-16 bg-bg-secondary/80 backdrop-blur-md border-b border-border-subtle flex items-center justify-between px-6 z-20">
      {/* Left: router status */}
      <div className="flex items-center gap-4">
        <ConnectionIndicator status={connectionStatus} />
      </div>

      {/* Right: controls */}
      <div className="flex items-center gap-2">
        {/* Language switcher */}
        <LanguageSwitcher />

        {/* Theme toggle */}
        <ThemeToggle />

        {/* Notifications */}
        <button
          className="btn-icon relative"
          aria-label={`${t.header_notifications}${unreadCount > 0 ? `, ${unreadCount} ${t.header_unread}` : ''}`}
        >
          <Bell className="w-5 h-5" strokeWidth={2} />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 min-w-[16px] h-4 flex items-center justify-center bg-status-danger text-white text-[10px] font-bold rounded-full px-1 ring-2 ring-bg-secondary">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </button>

        <div className="w-px h-8 bg-border-subtle" />

        {/* Admin profile */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-primary to-brand-secondary flex items-center justify-center text-white text-sm font-semibold shadow-sm">
            {adminName.charAt(0).toUpperCase()}
          </div>
          <span className="text-sm font-medium text-fg-primary hidden sm:block">{adminName}</span>
          <button
            onClick={onLogout}
            className="btn-icon"
            title={t.header_logout}
            aria-label={t.header_logout}
          >
            <LogOut className="w-4 h-4" strokeWidth={2} />
          </button>
        </div>
      </div>
    </header>
  );
}
