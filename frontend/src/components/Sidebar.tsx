import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Smartphone, Shield, BarChart3, Settings as SettingsIcon, Wifi, Network, ShieldCheck
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

export default function Sidebar() {
  const location = useLocation();
  const { t } = useLanguage();

  const navItems = [
    { label: t.nav_dashboard || 'Dashboard',    path: '/',            Icon: LayoutDashboard },
    { label: t.nav_devices || 'Devices',      path: '/devices',     Icon: Smartphone      },
    { label: t.nav_restrictions || 'Restrictions', path: '/restrictions', Icon: Shield         },
    { label: t.nav_analytics || 'Analytics',    path: '/analytics',   Icon: BarChart3       },
    { label: 'Network Map',   path: '/network-map', Icon: Network         },
    { label: 'Security & VPN', path: '/security',    Icon: ShieldCheck     },
    { label: t.nav_settings || 'Settings',     path: '/settings',    Icon: SettingsIcon    },
  ];

  const isActive = (path: string): boolean => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-bg-secondary border-r border-border-subtle flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border-subtle">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-primary to-brand-secondary flex items-center justify-center shadow-glow-blue">
            <Wifi className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-fg-primary leading-tight">SmartWiFi</h1>
            <p className="text-2xs text-fg-muted leading-tight">Network Dashboard</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const active = isActive(item.path);
          const Icon = item.Icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === '/'}
              className={active ? 'sidebar-link-active' : 'sidebar-link'}
            >
              <Icon className={`w-4 h-4 ${active ? 'text-brand-primary' : 'text-fg-muted'}`} strokeWidth={2} />
              <span className="text-sm font-medium">{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-border-subtle">
        <div className="flex items-center justify-between">
          <p className="text-2xs text-fg-subtle font-mono">v1.0.0</p>
          <div className="flex items-center gap-1.5">
            <div className="status-dot-success" />
            <span className="text-2xs text-fg-muted">{t.online}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
