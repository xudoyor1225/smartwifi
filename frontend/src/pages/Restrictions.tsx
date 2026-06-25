import { useState, useEffect, useCallback } from 'react';
import {
  Camera, Music2, Send, PlayCircle, Film, Globe, Loader2, AlertCircle, Save, Gauge
} from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

interface BlockingScenario {
  id: string;
  app_name: string;
  app_logo_url: string | null;
  is_active: boolean;
  version: number;
}

interface BandwidthConfig {
  global_download_mbps: number;
  global_upload_mbps: number;
  uplink_capacity_mbps: number;
  congestion_warning: boolean;
}

const APP_CONFIG: Record<string, { Icon: typeof Camera; gradient: string; descKey: string }> = {
  Instagram: { Icon: Camera,     gradient: 'from-pink-500 via-rose-500 to-orange-500', descKey: 'Photo & video sharing' },
  TikTok:    { Icon: Music2,     gradient: 'from-slate-800 via-pink-500 to-cyan-400',  descKey: 'Short-form video'      },
  Telegram:  { Icon: Send,       gradient: 'from-sky-400 to-blue-600',                 descKey: 'Messaging platform'    },
  YouTube:   { Icon: PlayCircle, gradient: 'from-red-500 to-red-700',                  descKey: 'Video streaming'       },
  Netflix:   { Icon: Film,       gradient: 'from-red-600 via-red-700 to-black',        descKey: 'Movie streaming'       },
};

export default function Restrictions() {
  const { t } = useLanguage();
  const [scenarios, setScenarios] = useState<BlockingScenario[]>([]);
  const [bandwidth, setBandwidth] = useState<BandwidthConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [bandwidthSaving, setBandwidthSaving] = useState(false);
  const [downloadLimit, setDownloadLimit] = useState(100);
  const [uploadLimit, setUploadLimit] = useState(50);

  const fetchData = useCallback(async () => {
    try {
      const [scenariosRes, bandwidthRes] = await Promise.allSettled([
        api.get('/blocking/scenarios'),
        api.get('/bandwidth/config'),
      ]);
      if (scenariosRes.status === 'fulfilled') setScenarios(scenariosRes.value.data.scenarios || []);
      if (bandwidthRes.status === 'fulfilled') {
        const config = bandwidthRes.value.data;
        setBandwidth(config);
        setDownloadLimit(config.global_download_mbps);
        setUploadLimit(config.global_upload_mbps);
      }
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(''), 3000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  const toggleScenario = async (id: string, currentlyActive: boolean) => {
    setPendingId(id);
    setError('');
    try {
      await api.post(`/blocking/scenarios/${id}/${currentlyActive ? 'deactivate' : 'activate'}`);
      await fetchData();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || "Amalni bajarib bo'lmadi");
      }
    } finally { setPendingId(null); }
  };

  const saveBandwidth = async () => {
    setBandwidthSaving(true);
    setError('');
    try {
      await api.put('/bandwidth/global', { download_mbps: downloadLimit, upload_mbps: uploadLimit });
      await fetchData();
      setSuccess(t.res_saved);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || 'Saqlashda xatolik');
      }
    } finally { setBandwidthSaving(false); }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-9 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {[1,2,3,4,5].map((i) => <div key={i} className="skeleton h-44 rounded-xl" />)}
        </div>
      </div>
    );
  }

  const blockedCount = scenarios.filter((s) => s.is_active).length;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="page-heading">{t.res_title}</h2>
        <p className="text-sm text-fg-muted mt-1">{t.res_subtitle}</p>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-status-dangerBg border border-status-danger/30 flex items-center gap-2.5 animate-slide-up">
          <AlertCircle className="w-4 h-4 text-status-danger flex-shrink-0" />
          <p className="text-sm text-status-danger">{error}</p>
        </div>
      )}
      {success && (
        <div className="p-3 rounded-lg bg-status-successBg border border-status-success/30 flex items-center gap-2.5 animate-slide-up">
          <div className="w-4 h-4 rounded-full bg-status-success/20 flex items-center justify-center">
            <span className="text-status-success text-xs">✓</span>
          </div>
          <p className="text-sm text-status-success">{success}</p>
        </div>
      )}

      {/* App Blocking */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="section-heading">{t.res_app_block_title}</h3>
            <p className="text-xs text-fg-muted mt-0.5">
              {blockedCount} {t.res_app_block_sub_a} {scenarios.length - blockedCount} {t.res_app_block_sub_b}
            </p>
          </div>
        </div>

        {scenarios.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            {scenarios.map((scenario) => {
              const config = APP_CONFIG[scenario.app_name] || { Icon: Globe, gradient: 'from-slate-500 to-slate-700', descKey: 'Application' };
              const Icon = config.Icon;
              const isPending = pendingId === scenario.id;
              return (
                <div key={scenario.id} className={`card-hover relative overflow-hidden ${scenario.is_active ? 'ring-1 ring-status-danger/40' : ''}`}>
                  <div className="flex flex-col items-center text-center mb-4">
                    <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${config.gradient} flex items-center justify-center mb-3 shadow-lg`}>
                      <Icon className="w-7 h-7 text-white" strokeWidth={2} />
                    </div>
                    <h4 className="text-sm font-semibold text-fg-primary">{scenario.app_name}</h4>
                    <p className="text-2xs text-fg-muted mt-0.5">{config.descKey}</p>
                  </div>
                  <div className="flex items-center justify-center mb-2">
                    <button
                      onClick={() => toggleScenario(scenario.id, scenario.is_active)}
                      disabled={isPending}
                      className={`toggle-switch ${scenario.is_active ? 'bg-status-danger' : 'bg-bg-tertiary border border-border-default'} ${isPending ? 'opacity-50' : ''}`}
                      aria-label={`${scenario.is_active ? 'Ochish' : 'Bloklash'} ${scenario.app_name}`}
                    >
                      <span className={`toggle-switch-thumb ${scenario.is_active ? 'translate-x-5' : ''}`}>
                        {isPending && <Loader2 className="w-3 h-3 text-fg-muted absolute top-1 left-1 animate-spin" />}
                      </span>
                    </button>
                  </div>
                  <p className={`text-2xs text-center font-medium uppercase tracking-wide ${scenario.is_active ? 'text-status-danger' : 'text-status-success'}`}>
                    {isPending ? t.res_pending : scenario.is_active ? t.res_blocked : t.res_allowed}
                  </p>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="card empty-state">
            <div className="empty-state-icon"><Globe className="w-7 h-7" /></div>
            <p className="text-sm text-fg-secondary">{t.res_no_scenarios}</p>
          </div>
        )}
      </section>

      {/* Bandwidth */}
      <section>
        <div className="mb-4">
          <h3 className="section-heading flex items-center gap-2">
            <Gauge className="w-4 h-4 text-brand-primary" />
            {t.res_bw_title}
          </h3>
          <p className="text-xs text-fg-muted mt-0.5">{t.res_bw_sub}</p>
        </div>
        <div className="card">
          {bandwidth?.congestion_warning && (
            <div className="mb-5 p-3 rounded-lg bg-status-warningBg border border-status-warning/30 flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-status-warning flex-shrink-0" />
              <p className="text-sm text-status-warning">{t.res_congestion}</p>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-fg-secondary uppercase tracking-wide">{t.res_download}</label>
                <span className="text-sm font-bold text-status-info font-mono">{downloadLimit} <span className="text-fg-muted">Mbps</span></span>
              </div>
              <input type="range" min={1} max={1000} value={downloadLimit} onChange={(e) => setDownloadLimit(Number(e.target.value))}
                className="w-full h-1.5 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-status-info" />
              <div className="flex justify-between text-2xs text-fg-subtle mt-1"><span>1 Mbps</span><span>500 Mbps</span><span>1000 Mbps</span></div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-medium text-fg-secondary uppercase tracking-wide">{t.res_upload}</label>
                <span className="text-sm font-bold text-status-success font-mono">{uploadLimit} <span className="text-fg-muted">Mbps</span></span>
              </div>
              <input type="range" min={1} max={1000} value={uploadLimit} onChange={(e) => setUploadLimit(Number(e.target.value))}
                className="w-full h-1.5 bg-bg-tertiary rounded-lg appearance-none cursor-pointer accent-status-success" />
              <div className="flex justify-between text-2xs text-fg-subtle mt-1"><span>1 Mbps</span><span>500 Mbps</span><span>1000 Mbps</span></div>
            </div>
          </div>
          <div className="mt-6 pt-4 border-t border-border-subtle flex items-center justify-between flex-wrap gap-3">
            <p className="text-xs text-fg-muted">
              <span className="font-medium text-fg-secondary">{t.res_uplink}:</span>{' '}
              <span className="font-mono">{bandwidth?.uplink_capacity_mbps || 1000} Mbps</span>
            </p>
            <button onClick={saveBandwidth} disabled={bandwidthSaving} className="btn-primary flex items-center gap-2">
              {bandwidthSaving ? (<><Loader2 className="w-4 h-4 animate-spin" />{t.res_saving}</>) : (<><Save className="w-4 h-4" />{t.res_save}</>)}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
