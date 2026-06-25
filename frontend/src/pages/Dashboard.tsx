import {
  Smartphone, Download, Upload, Activity, AlertTriangle, Brain, TrendingUp, Wifi, Globe,
} from 'lucide-react';
import { useNetwork, useStats, useDevices } from '../context/NetworkContext';
import { useLanguage } from '../context/LanguageContext';
import TrafficChart from '../components/TrafficChart';

const formatBytes = (bytes: number): string => {
  if (bytes >= 1099511627776) return `${(bytes / 1099511627776).toFixed(2)} TB`;
  if (bytes >= 1073741824)    return `${(bytes / 1073741824).toFixed(2)} GB`;
  if (bytes >= 1048576)       return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024)          return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
};

export default function Dashboard() {
  const { stats, trafficHistory } = useStats();
  const { devices, isInitialLoading } = useDevices();
  const { alerts } = useNetwork();
  const { t } = useLanguage();

  const showWarning = stats.ping_ms > 100 || stats.jitter_ms > 50;

  if (isInitialLoading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-9 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1,2,3,4].map((i) => <div key={i} className="skeleton h-28 rounded-xl" />)}
        </div>
        <div className="skeleton h-80 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="page-heading">{t.dash_title}</h2>
          <p className="text-sm text-fg-muted mt-1">{t.dash_subtitle}</p>
        </div>
        {stats.local_ip && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-bg-secondary rounded-lg border border-border-subtle">
            <Globe className="w-3.5 h-3.5 text-fg-muted" />
            <span className="text-xs font-mono text-fg-secondary">{stats.subnet || stats.local_ip}</span>
          </div>
        )}
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Devices */}
        <div className="card-stat">
          <div className="flex items-start justify-between mb-3">
            <div className="w-10 h-10 rounded-lg bg-brand-primary/10 border border-brand-primary/20 flex items-center justify-center">
              <Smartphone className="w-5 h-5 text-brand-primary" />
            </div>
          </div>
          <p className="text-3xl font-bold text-fg-primary tabular-nums">{devices.length}</p>
          <p className="text-sm text-fg-muted mt-1">{t.dash_connected_devices}</p>
        </div>

        {/* Download */}
        <div className="card-stat">
          <div className="flex items-start justify-between mb-3">
            <div className="w-10 h-10 rounded-lg bg-status-infoBg border border-status-info/20 flex items-center justify-center">
              <Download className="w-5 h-5 text-status-info" />
            </div>
            <span className="badge-info text-2xs">↓ DOWN</span>
          </div>
          <p className="text-3xl font-bold text-fg-primary tabular-nums">
            {stats.download_mbps.toFixed(1)}<span className="text-sm font-normal text-fg-muted ml-1">Mbps</span>
          </p>
          <p className="text-sm text-fg-muted mt-1">{t.dash_total}: {formatBytes(stats.bytes_recv)}</p>
        </div>

        {/* Upload */}
        <div className="card-stat">
          <div className="flex items-start justify-between mb-3">
            <div className="w-10 h-10 rounded-lg bg-status-successBg border border-status-success/20 flex items-center justify-center">
              <Upload className="w-5 h-5 text-status-success" />
            </div>
            <span className="badge-success text-2xs">↑ UP</span>
          </div>
          <p className="text-3xl font-bold text-fg-primary tabular-nums">
            {stats.upload_mbps.toFixed(1)}<span className="text-sm font-normal text-fg-muted ml-1">Mbps</span>
          </p>
          <p className="text-sm text-fg-muted mt-1">{t.dash_total}: {formatBytes(stats.bytes_sent)}</p>
        </div>

        {/* Quality */}
        <div className={`card-stat ${showWarning ? 'border-status-danger/30' : ''}`}>
          <div className="flex items-start justify-between mb-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${showWarning ? 'bg-status-dangerBg border border-status-danger/20' : 'bg-status-successBg border border-status-success/20'}`}>
              <Activity className={`w-5 h-5 ${showWarning ? 'text-status-danger' : 'text-status-success'}`} />
            </div>
            {showWarning && <span className="badge-danger text-2xs">{t.dash_bad}</span>}
          </div>
          <p className={`text-3xl font-bold tabular-nums ${stats.ping_ms === 0 ? 'text-fg-muted' : showWarning ? 'text-status-danger' : 'text-fg-primary'}`}>
            {stats.ping_ms === 0 ? '—' : stats.ping_ms.toFixed(0)}
            {stats.ping_ms > 0 && <span className="text-sm font-normal text-fg-muted ml-1">ms</span>}
          </p>
          <p className="text-sm text-fg-muted mt-1">{t.dash_jitter}: {stats.jitter_ms.toFixed(1)} ms</p>
        </div>

        {/* AI Health Score */}
        <div className={`card-stat ${stats.ai_health && stats.ai_health.score < 60 ? 'border-status-warning/30' : ''}`}>
          <div className="flex items-start justify-between mb-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              !stats.ai_health ? 'bg-bg-secondary border border-border-subtle' :
              stats.ai_health.score >= 75 ? 'bg-brand-primary/10 border border-brand-primary/20' : 
              stats.ai_health.score >= 60 ? 'bg-status-warningBg border border-status-warning/20' :
              'bg-status-dangerBg border border-status-danger/20'
            }`}>
              <Brain className={`w-5 h-5 ${
                !stats.ai_health ? 'text-fg-muted' :
                stats.ai_health.score >= 75 ? 'text-brand-primary' : 
                stats.ai_health.score >= 60 ? 'text-status-warning' :
                'text-status-danger'
              }`} />
            </div>
            {stats.ai_health && (
              <span className={
                stats.ai_health.score >= 75 ? "badge-success text-2xs" : 
                stats.ai_health.score >= 60 ? "badge-warning text-2xs" : 
                "badge-danger text-2xs"
              }>{stats.ai_health.status}</span>
            )}
          </div>
          <p className={`text-3xl font-bold tabular-nums ${!stats.ai_health ? 'text-fg-muted' : 'text-fg-primary'}`}>
            {stats.ai_health ? stats.ai_health.score : '—'}<span className="text-sm font-normal text-fg-muted ml-1">/100</span>
          </p>
          <p className="text-sm text-fg-muted mt-1">{t.dash_ai_health_sub}: {stats.ai_health ? (stats.ai_health.issues.length > 0 ? `${stats.ai_health.issues.length} issue(s)` : 'Optimal') : 'Learning...'}</p>
        </div>
      </div>

      {/* Charts + Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Traffic Chart */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h3 className="section-heading flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-brand-primary" />
                {t.dash_traffic}
              </h3>
              <p className="text-xs text-fg-muted mt-0.5">{t.dash_traffic_sub}</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-chart-blue shadow-[0_0_6px_rgba(59,130,246,0.6)]" />
                <span className="text-fg-muted tabular-nums">↓ {stats.download_mbps.toFixed(2)}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-chart-emerald shadow-[0_0_6px_rgba(16,185,129,0.6)]" />
                <span className="text-fg-muted tabular-nums">↑ {stats.upload_mbps.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {trafficHistory.length > 1 ? (
            <TrafficChart data={trafficHistory} height={280} />
          ) : (
            <div className="empty-state h-72">
              <div className="empty-state-icon"><Wifi className="w-7 h-7" /></div>
              <p className="text-sm text-fg-secondary">{t.dash_collecting}</p>
              <p className="text-xs text-fg-muted mt-1">{t.dash_chart_soon}</p>
            </div>
          )}
        </div>

        {/* AI Alerts */}
        <div className="card">
          <div className="flex items-center justify-between mb-5">
            <h3 className="section-heading flex items-center gap-2">
              <Brain className="w-4 h-4 text-brand-secondary" />
              {t.dash_ai_alerts}
            </h3>
            {alerts.length > 0 && <span className="badge-info">{alerts.length}</span>}
          </div>

          {alerts.length > 0 ? (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {alerts.slice(0, 5).map((alert) => {
                const severityClass =
                  alert.severity === 'high'   ? 'border-status-danger/30 bg-status-dangerBg' :
                  alert.severity === 'medium' ? 'border-status-warning/30 bg-status-warningBg' :
                  'border-status-info/30 bg-status-infoBg';
                const iconClass =
                  alert.severity === 'high'   ? 'text-status-danger' :
                  alert.severity === 'medium' ? 'text-status-warning' :
                  'text-status-info';
                return (
                  <div key={alert.id} className={`p-3 rounded-lg border ${severityClass}`}>
                    <div className="flex items-start gap-2.5">
                      <AlertTriangle className={`w-4 h-4 ${iconClass} flex-shrink-0 mt-0.5`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-fg-primary font-medium">{alert.anomaly_type}</p>
                        {alert.description && <p className="text-xs text-fg-muted mt-0.5">{alert.description}</p>}
                        <p className="text-2xs text-fg-subtle mt-1">
                          {new Date(alert.detected_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon"><Brain className="w-7 h-7" /></div>
              <p className="text-sm text-fg-secondary">{t.dash_no_alerts}</p>
              <p className="text-xs text-fg-muted mt-1">{t.dash_network_ok}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
