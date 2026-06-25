import { useState, useEffect, useCallback } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import {
  Brain, AlertTriangle, FileText, FileSpreadsheet, Loader2, TrendingUp, Activity, Calendar,
} from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

interface TrafficCategory { category: string; bytes_total: number; percentage: number; }
interface AnomalyAlert { id: string; severity: string; anomaly_type: string; description: string | null; observed_value: number; baseline_value: number; detected_at: string; }
interface BaselineStatus { has_baseline: boolean; days_of_data: number; required_days: number; message: string; }

const CATEGORY_COLORS: Record<string, string> = {
  Video: '#3B82F6', 'Social Media': '#8B5CF6', 'Web Browsing': '#06B6D4',
  Gaming: '#10B981', 'File Transfer': '#F59E0B', Other: '#F43F5E',
};

export default function Analytics() {
  const { t } = useLanguage();
  const [period, setPeriod] = useState<'24h' | '7d'>('24h');
  const [categories, setCategories] = useState<TrafficCategory[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyAlert[]>([]);
  const [baseline, setBaseline] = useState<BaselineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [trafficRes, anomalyRes, baselineRes] = await Promise.allSettled([
        api.get(`/analytics/traffic?period=${period}`),
        api.get(`/analytics/anomalies?period=${period}`),
        api.get('/analytics/baseline-status'),
      ]);
      if (trafficRes.status === 'fulfilled') setCategories(trafficRes.value.data.categories || []);
      if (anomalyRes.status === 'fulfilled') setAnomalies(anomalyRes.value.data.alerts || []);
      if (baselineRes.status === 'fulfilled') setBaseline(baselineRes.value.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [period]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleExport = async (format: 'pdf' | 'excel') => {
    setExporting(format);
    try { await new Promise((r) => setTimeout(r, 1500)); }
    finally { setExporting(null); }
  };

  const hasTrafficData = categories.some((c) => c.bytes_total > 0);
  const pieData = categories.map((c) => ({ name: c.category, value: c.percentage || 0 }));

  const severityConfig: Record<string, { bg: string; text: string; icon: string }> = {
    high:   { bg: 'bg-status-dangerBg border-status-danger/30',   text: 'text-status-danger',  icon: '🚨' },
    medium: { bg: 'bg-status-warningBg border-status-warning/30', text: 'text-status-warning', icon: '⚠️' },
    low:    { bg: 'bg-status-infoBg border-status-info/30',       text: 'text-status-info',    icon: 'ℹ️' },
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-9 w-48" />
        <div className="skeleton h-20 rounded-xl" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="skeleton h-80 rounded-xl" /><div className="skeleton h-80 rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="page-heading">{t.ana_title}</h2>
          <p className="text-sm text-fg-muted mt-1">{t.ana_subtitle}</p>
        </div>
        <div className="flex items-center gap-2 p-1 bg-bg-secondary rounded-lg border border-border-subtle">
          <button
            onClick={() => setPeriod('24h')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${period === '24h' ? 'bg-brand-primary text-white shadow-sm' : 'text-fg-muted hover:text-fg-primary'}`}
          >
            <Calendar className="w-3 h-3 inline mr-1" />{t.ana_24h}
          </button>
          <button
            onClick={() => setPeriod('7d')}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${period === '7d' ? 'bg-brand-primary text-white shadow-sm' : 'text-fg-muted hover:text-fg-primary'}`}
          >
            <Calendar className="w-3 h-3 inline mr-1" />{t.ana_7d}
          </button>
        </div>
      </div>

      {/* Baseline */}
      {baseline && (
        <div className={`card flex items-center gap-4 ${baseline.has_baseline ? 'bg-gradient-to-r from-brand-primary/5 to-brand-secondary/5 border-brand-primary/20' : 'bg-status-warningBg border-status-warning/20'}`}>
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${baseline.has_baseline ? 'bg-gradient-to-br from-brand-primary/20 to-brand-secondary/20' : 'bg-status-warningBg'}`}>
            <Brain className={`w-6 h-6 ${baseline.has_baseline ? 'text-brand-secondary' : 'text-status-warning'}`} />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-fg-primary">{baseline.has_baseline ? t.ana_ai_active : t.ana_ai_learning}</p>
            <p className="text-xs text-fg-muted mt-0.5">{baseline.message}</p>
          </div>
          <div className="text-right">
            <p className="text-2xs text-fg-muted uppercase tracking-wide">{t.ana_data}</p>
            <p className="text-lg font-bold text-fg-primary">
              {baseline.days_of_data}<span className="text-xs text-fg-muted">/{baseline.required_days} {t.ana_days}</span>
            </p>
          </div>
        </div>
      )}

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Traffic Distribution */}
        <div className="card">
          <div className="flex items-center justify-between mb-5">
            <h3 className="section-heading flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-brand-primary" />{t.ana_traffic_dist}
            </h3>
          </div>
          {hasTrafficData ? (
            <>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={70} outerRadius={100} dataKey="value" paddingAngle={2}>
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={CATEGORY_COLORS[entry.name] || '#64748B'} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#0F1623', border: '1px solid #293548', borderRadius: '8px', color: '#F8FAFC', fontSize: '12px' }}
                      formatter={(value: number) => `${value}%`}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-border-subtle">
                {categories.map((cat) => (
                  <div key={cat.category} className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: CATEGORY_COLORS[cat.category] || '#64748B' }} />
                    <span className="text-xs text-fg-secondary flex-1 truncate">{cat.category}</span>
                    <span className="text-xs font-semibold text-fg-primary font-mono">{cat.percentage}%</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state h-64">
              <div className="empty-state-icon"><Activity className="w-7 h-7" /></div>
              <p className="text-sm text-fg-secondary">{t.ana_no_traffic}</p>
              <p className="text-xs text-fg-muted mt-1 max-w-xs">{t.ana_mikrotik_needed}</p>
            </div>
          )}
        </div>

        {/* Anomalies */}
        <div className="card">
          <div className="flex items-center justify-between mb-5">
            <h3 className="section-heading flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-status-warning" />{t.ana_anomalies}
            </h3>
            {anomalies.length > 0 && <span className="badge-warning">{anomalies.length}</span>}
          </div>
          {anomalies.length > 0 ? (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {anomalies.map((anomaly) => {
                const config = severityConfig[anomaly.severity] || severityConfig.low;
                return (
                  <div key={anomaly.id} className={`p-3 rounded-lg border ${config.bg}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm font-medium ${config.text}`}>{config.icon} {anomaly.anomaly_type}</p>
                        {anomaly.description && <p className="text-xs text-fg-muted mt-0.5">{anomaly.description}</p>}
                      </div>
                      <span className="text-2xs text-fg-subtle whitespace-nowrap">
                        {new Date(anomaly.detected_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="empty-state h-64">
              <div className="empty-state-icon"><AlertTriangle className="w-7 h-7" /></div>
              <p className="text-sm text-fg-secondary">{t.ana_no_anomalies}</p>
              <p className="text-xs text-fg-muted mt-1">{t.ana_network_ok}</p>
            </div>
          )}
        </div>
      </div>

      {/* Export */}
      <div className="card">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h3 className="section-heading flex items-center gap-2">
              <FileText className="w-4 h-4 text-brand-primary" />{t.ana_export_title}
            </h3>
            <p className="text-xs text-fg-muted mt-1">{t.ana_export_sub}</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => handleExport('pdf')} disabled={exporting === 'pdf'} className="btn-secondary flex items-center gap-2">
              {exporting === 'pdf' ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              {t.ana_export_pdf}
            </button>
            <button onClick={() => handleExport('excel')} disabled={exporting === 'excel'} className="btn-secondary flex items-center gap-2">
              {exporting === 'excel' ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
              {t.ana_export_excel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
