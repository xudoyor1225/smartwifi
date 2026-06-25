import { useState, useMemo } from 'react';
import {
  Smartphone, Wifi, Ban, Power, RefreshCw, AlertCircle, Search,
  Monitor, Tablet, Tv, Laptop, Router as RouterIcon, Cpu,
} from 'lucide-react';
import api from '../services/api';
import { useDevices, useStats, type LocalDevice } from '../context/NetworkContext';
import { useLanguage } from '../context/LanguageContext';

const getDeviceIcon = (device: { manufacturer: string; hostname: string | null; is_self: boolean; is_gateway: boolean }) => {
  if (device.is_gateway) return RouterIcon;
  if (device.is_self) return Laptop;
  const m = device.manufacturer.toLowerCase();
  const h = (device.hostname || '').toLowerCase();
  if (m.includes('apple') || h.includes('iphone') || h.includes('ipad') || h.includes('mac')) {
    if (h.includes('ipad')) return Tablet;
    if (h.includes('mac') || h.includes('book')) return Laptop;
    return Smartphone;
  }
  if (m.includes('samsung') || m.includes('xiaomi') || h.includes('android')) return Smartphone;
  if (m.includes('mobile') || m.includes('random')) return Smartphone;
  if (m.includes('lg') || h.includes('tv')) return Tv;
  if (m.includes('mikrotik') || m.includes('cisco') || m.includes('tp-link') || m.includes('netgear')) return RouterIcon;
  if (m.includes('raspberry')) return Cpu;
  if (m.includes('liteon') || m.includes('laptop')) return Laptop;
  return Monitor;
};

const getManufacturerColor = (device: { manufacturer: string; is_self: boolean; is_gateway: boolean }): string => {
  if (device.is_gateway) return 'from-cyan-500 to-blue-600';
  if (device.is_self) return 'from-brand-primary to-brand-secondary';
  const m = device.manufacturer.toLowerCase();
  if (m.includes('apple')) return 'from-gray-400 to-gray-600';
  if (m.includes('samsung')) return 'from-blue-500 to-blue-700';
  if (m.includes('xiaomi')) return 'from-orange-500 to-orange-700';
  if (m.includes('lg')) return 'from-rose-500 to-rose-700';
  if (m.includes('mikrotik')) return 'from-cyan-500 to-cyan-700';
  if (m.includes('tp-link')) return 'from-emerald-500 to-emerald-700';
  if (m.includes('cisco')) return 'from-indigo-500 to-indigo-700';
  if (m.includes('raspberry')) return 'from-pink-500 to-pink-700';
  if (m.includes('mobile') || m.includes('random')) return 'from-violet-500 to-purple-700';
  if (m.includes('liteon') || m.includes('laptop')) return 'from-slate-400 to-slate-600';
  return 'from-slate-500 to-slate-700';
};

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '—';
  if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
  if (bytes >= 1048576)    return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024)       return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
};

export default function Devices() {
  const { devices, refreshDevices, isInitialLoading } = useDevices();
  const { stats } = useStats();
  const { t } = useLanguage();
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const enrichedDevices = useMemo(() => {
    const responsive = devices.filter((d) => d.is_responsive && !d.is_self);
    const totalRecv = stats.bytes_recv;
    const totalSent = stats.bytes_sent;
    const totalCount = Math.max(responsive.length, 1);
    return devices.map((d: LocalDevice) => {
      let estimatedBytes = d.bytes_total;
      if (d.is_self) estimatedBytes = totalRecv + totalSent;
      else if (d.is_responsive) estimatedBytes = Math.floor((totalRecv + totalSent) / totalCount / 4);
      return { ...d, estimated_bytes: estimatedBytes };
    });
  }, [devices, stats.bytes_recv, stats.bytes_sent]);

  const filteredDevices = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return enrichedDevices;
    return enrichedDevices.filter(
      (d) => d.ip_address.toLowerCase().includes(q) || d.mac_address.toLowerCase().includes(q) ||
             (d.hostname || '').toLowerCase().includes(q) || d.manufacturer.toLowerCase().includes(q)
    );
  }, [enrichedDevices, search]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshDevices();
    setTimeout(() => setRefreshing(false), 500);
  };

  const handleAction = async (mac: string, action: 'kick' | 'block' | 'unblock') => {
    setActionLoading(`${mac}-${action}`);
    setError('');
    try {
      await api.post(`/devices/${mac}/${action}`);
      await refreshDevices();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || 'Bu amal MikroTik router talab qiladi');
      }
    } finally {
      setActionLoading(null);
    }
  };

  const summary = useMemo(() => ({
    total: devices.length,
    active: devices.filter((d) => d.is_responsive || d.is_self).length,
    blocked: 0,
    vip: 0,
  }), [devices]);

  if (isInitialLoading && devices.length === 0) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-9 w-48" />
        <div className="skeleton h-12 rounded-lg" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1,2,3,4].map((i) => <div key={i} className="skeleton h-20 rounded-xl" />)}
        </div>
        <div className="space-y-2">
          {[1,2,3].map((i) => <div key={i} className="skeleton h-16 rounded-lg" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="page-heading">{t.dev_title}</h2>
          <p className="text-sm text-fg-muted mt-1">
            {stats.subnet ? `Subnet: ${stats.subnet} • ` : ''}
            {filteredDevices.length} {t.dev_subtitle}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-muted pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.dev_search}
              className="input-field pl-9 py-2 text-sm w-64"
            />
          </div>
          <button onClick={handleRefresh} disabled={refreshing} className="btn-secondary flex items-center gap-2 py-2">
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {t.dev_refresh}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-status-warningBg border border-status-warning/30 flex items-center gap-2.5">
          <AlertCircle className="w-4 h-4 text-status-warning flex-shrink-0" />
          <p className="text-sm text-status-warning">{error}</p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card py-3">
          <p className="text-2xs text-fg-muted uppercase tracking-wide">{t.dev_total}</p>
          <p className="text-2xl font-bold text-fg-primary mt-1 tabular-nums">{summary.total}</p>
        </div>
        <div className="card py-3">
          <p className="text-2xs text-fg-muted uppercase tracking-wide">{t.dev_active}</p>
          <p className="text-2xl font-bold text-status-success mt-1 tabular-nums">{summary.active}</p>
        </div>
        <div className="card py-3">
          <p className="text-2xs text-fg-muted uppercase tracking-wide">{t.dev_blocked}</p>
          <p className="text-2xl font-bold text-status-danger mt-1 tabular-nums">{summary.blocked}</p>
        </div>
        <div className="card py-3">
          <p className="text-2xs text-fg-muted uppercase tracking-wide">{t.dev_vip}</p>
          <p className="text-2xl font-bold text-brand-secondary mt-1 tabular-nums">{summary.vip}</p>
        </div>
      </div>

      {filteredDevices.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state-icon"><Wifi className="w-7 h-7" /></div>
          <p className="text-sm text-fg-secondary">{t.dev_no_devices}</p>
          <p className="text-xs text-fg-muted mt-1 max-w-md">{t.dev_arp_scan}</p>
        </div>
      ) : (
        <div className="card overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border-subtle bg-bg-tertiary/50">
                  {[t.dev_col_device, t.dev_col_ip, t.dev_col_mac, t.dev_col_status, t.dev_col_traffic].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-2xs font-semibold text-fg-muted uppercase tracking-wide">{h}</th>
                  ))}
                  <th className="text-right px-4 py-3 text-2xs font-semibold text-fg-muted uppercase tracking-wide">{t.dev_col_actions}</th>
                </tr>
              </thead>
              <tbody>
                {filteredDevices.map((device) => {
                  const Icon = getDeviceIcon(device);
                  const colorClass = getManufacturerColor(device);
                  const isActive = device.is_responsive || device.is_self;
                  return (
                    <tr key={device.mac_address} className="border-b border-border-subtle/50 hover:bg-bg-hover/40 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${colorClass} flex items-center justify-center flex-shrink-0`}>
                            <Icon className="w-4 h-4 text-white" />
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <p className="text-sm font-medium text-fg-primary truncate">{device.hostname || device.manufacturer}</p>
                              {device.is_self && <span className="badge-info text-2xs">{t.dev_this_pc}</span>}
                              {device.is_gateway && <span className="badge-warning text-2xs">{t.dev_gateway}</span>}
                            </div>
                            <p className="text-xs text-fg-muted">{device.manufacturer}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3"><span className="text-sm text-fg-secondary font-mono">{device.ip_address}</span></td>
                      <td className="px-4 py-3"><span className="text-xs text-fg-muted font-mono">{device.mac_address}</span></td>
                      <td className="px-4 py-3">
                        {isActive ? (
                          <span className="badge-success"><span className="w-1.5 h-1.5 rounded-full bg-status-success" />{t.dev_status_active}</span>
                        ) : (
                          <span className="badge-warning"><span className="w-1.5 h-1.5 rounded-full bg-status-warning" />{t.dev_status_inactive}</span>
                        )}
                      </td>
                      <td className="px-4 py-3"><span className="text-sm text-fg-secondary font-mono tabular-nums">{formatBytes(device.estimated_bytes)}</span></td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          {!device.is_self && !device.is_gateway && (
                            <>
                              <button
                                onClick={() => handleAction(device.mac_address, 'kick')}
                                disabled={actionLoading === `${device.mac_address}-kick`}
                                className="btn-icon text-status-warning hover:bg-status-warningBg disabled:opacity-30"
                                title={t.dev_kick}
                              ><Power className="w-4 h-4" /></button>
                              <button
                                onClick={() => handleAction(device.mac_address, 'block')}
                                disabled={actionLoading === `${device.mac_address}-block`}
                                className="btn-icon text-status-danger hover:bg-status-dangerBg disabled:opacity-30"
                                title={t.dev_block}
                              ><Ban className="w-4 h-4" /></button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {filteredDevices.length > 0 && (
        <div className="p-4 rounded-lg bg-status-infoBg border border-status-info/20">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-status-info flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-fg-primary">{t.dev_info_title}</p>
              <p className="text-xs text-fg-muted mt-1">{t.dev_info_desc}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
