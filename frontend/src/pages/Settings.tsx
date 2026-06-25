import { useState, useEffect, useCallback, type FormEvent } from 'react';
import {
  Router as RouterIcon, Wifi, Shield, AlertCircle, CheckCircle2, Loader2, Save, Zap, Info, ExternalLink, Lock
} from 'lucide-react';
import api from '../services/api';
import { useLanguage } from '../context/LanguageContext';

interface RouterConfigData {
  ip_address: string; api_port: number; api_username: string;
  connection_status: string; last_connected: string | null;
}

export default function Settings() {
  const { t } = useLanguage();
  const [ipAddress, setIpAddress] = useState('');
  const [apiPort, setApiPort] = useState('8728');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [testStatus, setTestStatus] = useState<'idle'|'testing'|'success'|'error'>('idle');
  const [testMessage, setTestMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [currentConfig, setCurrentConfig] = useState<RouterConfigData | null>(null);

  // Dashboard password state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [dashPassError, setDashPassError] = useState('');
  const [dashPassStatus, setDashPassStatus] = useState<'idle'|'saving'|'success'|'error'>('idle');
  const [dashPassMsg, setDashPassMsg] = useState('');

  const fetchConfig = useCallback(async () => {
    try {
      const response = await api.get('/settings/router');
      const config: RouterConfigData = response.data;
      setCurrentConfig(config);
      setIpAddress(config.ip_address);
      setApiPort(String(config.api_port));
      setUsername(config.api_username);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) setCurrentConfig(null);
      }
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    const ipPattern = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
    const ipMatch = ipAddress.match(ipPattern);
    if (!ipAddress) newErrors.ip = t.val_ip_required;
    else if (!ipMatch) newErrors.ip = t.val_ip_format;
    else {
      const octets = [parseInt(ipMatch[1]), parseInt(ipMatch[2]), parseInt(ipMatch[3]), parseInt(ipMatch[4])];
      if (octets.some((o) => o < 0 || o > 255)) newErrors.ip = t.val_ip_range;
    }
    const port = parseInt(apiPort);
    if (!apiPort) newErrors.port = t.val_port_required;
    else if (isNaN(port) || port < 1 || port > 65535) newErrors.port = t.val_port_range;
    if (!username) newErrors.username = t.val_user_required;
    if (!password && !currentConfig) newErrors.password = t.val_pass_required;
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async (e: FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;
    setSaving(true);
    setTestStatus('idle');
    try {
      await api.put('/settings/router', { ip_address: ipAddress, api_port: parseInt(apiPort), api_username: username, api_password: password || 'unchanged' });
      setTestStatus('success');
      setTestMessage(t.set_saved_ok);
      await fetchConfig();
    } catch (err: unknown) {
      setTestStatus('error');
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setTestMessage(axiosErr.response?.data?.detail || 'Saqlashda xatolik');
      } else { setTestMessage("Server bilan bog'lanib bo'lmadi"); }
    } finally { setSaving(false); }
  };

  const handleTestConnection = async () => {
    if (!currentConfig && !validateForm()) return;
    setTestStatus('testing');
    setTestMessage('Routerga ulanish tekshirilmoqda...');
    try {
      const response = await api.post('/settings/router/test');
      const { status, message, latency_ms } = response.data;
      if (status === 'success') {
        setTestStatus('success');
        setTestMessage(`Muvaffaqiyatli ulandi (latency: ${latency_ms}ms)`);
        await fetchConfig();
      } else { setTestStatus('error'); setTestMessage(message || 'Ulanish muvaffaqiyatsiz'); }
    } catch (err: unknown) {
      setTestStatus('error');
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        if (axiosErr.response?.status === 404) setTestMessage('Avval konfiguratsiyani saqlang');
        else setTestMessage(axiosErr.response?.data?.detail || 'Ulanish tekshiruvi muvaffaqiyatsiz');
      } else { setTestMessage("Serverga ulanib bo'lmadi"); }
    }
  };

  const handleUpdateDashboardPassword = async (e: FormEvent) => {
    e.preventDefault();
    setDashPassError('');
    if (!currentPassword || !newPassword) {
      setDashPassError('Barcha maydonlarni to\'ldiring');
      return;
    }
    if (newPassword.length < 6) {
      setDashPassError('Yangi parol kamida 6 ta belgidan iborat bo\'lishi kerak');
      return;
    }

    setDashPassStatus('saving');
    try {
      await api.put('/auth/password', {
        current_password: currentPassword,
        new_password: newPassword
      });
      setDashPassStatus('success');
      setDashPassMsg(t.set_dash_pass_ok || 'Parol muvaffaqiyatli o\'zgartirildi!');
      setCurrentPassword('');
      setNewPassword('');
      setTimeout(() => setDashPassStatus('idle'), 3000);
    } catch (err: unknown) {
      setDashPassStatus('error');
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setDashPassMsg(axiosErr.response?.data?.detail || 'Xatolik yuz berdi');
      } else {
        setDashPassMsg('Server bilan bog\'lanib bo\'lmadi');
      }
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-9 w-48" />
        <div className="skeleton h-32 rounded-xl" />
        <div className="skeleton h-96 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="page-heading">{t.set_title}</h2>
        <p className="text-sm text-fg-muted mt-1">{t.set_subtitle}</p>
      </div>

      {currentConfig && (
        <div className={`card flex items-center gap-4 ${currentConfig.connection_status === 'connected' ? 'bg-gradient-to-r from-status-successBg to-bg-secondary border-status-success/20' : ''}`}>
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${currentConfig.connection_status === 'connected' ? 'bg-status-successBg' : 'bg-status-dangerBg'}`}>
            <RouterIcon className={`w-6 h-6 ${currentConfig.connection_status === 'connected' ? 'text-status-success' : 'text-status-danger'}`} />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-semibold text-fg-primary">
                {currentConfig.connection_status === 'connected' ? t.set_router_connected : t.set_router_disconnected}
              </p>
              {currentConfig.connection_status === 'connected' ? (
                <span className="badge-success"><span className="status-dot-success" />{t.online}</span>
              ) : (
                <span className="badge-danger"><span className="status-dot-danger" />{t.offline}</span>
              )}
            </div>
            <p className="text-xs text-fg-muted mt-1 font-mono">{currentConfig.ip_address}:{currentConfig.api_port}</p>
          </div>
          {currentConfig.last_connected && (
            <div className="text-right">
              <p className="text-2xs text-fg-muted uppercase tracking-wide">{t.set_last_conn}</p>
              <p className="text-xs text-fg-secondary mt-1">{new Date(currentConfig.last_connected).toLocaleString()}</p>
            </div>
          )}
        </div>
      )}

      {!currentConfig && (
        <div className="card bg-status-infoBg border-status-info/20">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-status-info/10 flex items-center justify-center flex-shrink-0">
              <Info className="w-5 h-5 text-status-info" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold text-fg-primary">{t.set_info_title}</p>
              <p className="text-xs text-fg-muted mt-1">{t.set_info_sub}</p>
              <a href="https://help.mikrotik.com/docs/display/ROS/API" target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-brand-primary hover:underline mt-2">
                {t.set_docs}<ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="mb-6">
          <h3 className="section-heading flex items-center gap-2">
            <Shield className="w-4 h-4 text-brand-primary" />{t.set_config_title}
          </h3>
          <p className="text-xs text-fg-muted mt-1">{t.set_config_sub}</p>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label htmlFor="ip" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">{t.set_ip_label}</label>
              <div className="relative">
                <Wifi className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-muted pointer-events-none" />
                <input id="ip" type="text" value={ipAddress}
                  onChange={(e) => { setIpAddress(e.target.value); setErrors((p) => ({ ...p, ip: '' })); }}
                  placeholder="192.168.88.1" className={`${errors.ip ? 'input-field-error' : 'input-field'} pl-10`} />
              </div>
              {errors.ip && <p className="text-status-danger text-xs mt-1.5 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{errors.ip}</p>}
            </div>
            <div>
              <label htmlFor="port" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">{t.set_port_label}</label>
              <input id="port" type="number" value={apiPort}
                onChange={(e) => { setApiPort(e.target.value); setErrors((p) => ({ ...p, port: '' })); }}
                placeholder="8728" min={1} max={65535} className={errors.port ? 'input-field-error' : 'input-field'} />
              {errors.port && <p className="text-status-danger text-xs mt-1.5">{errors.port}</p>}
            </div>
          </div>

          <div>
            <label htmlFor="api-username" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">{t.set_user_label}</label>
            <input id="api-username" type="text" value={username}
              onChange={(e) => { setUsername(e.target.value); setErrors((p) => ({ ...p, username: '' })); }}
              placeholder="admin" autoComplete="off" className={errors.username ? 'input-field-error' : 'input-field'} />
            {errors.username && <p className="text-status-danger text-xs mt-1.5">{errors.username}</p>}
          </div>

          <div>
            <label htmlFor="api-password" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">
              {t.set_pass_label}
              {currentConfig && <span className="ml-2 text-fg-muted normal-case font-normal">{t.set_pass_change_hint}</span>}
            </label>
            <input id="api-password" type="password" value={password}
              onChange={(e) => { setPassword(e.target.value); setErrors((p) => ({ ...p, password: '' })); }}
              placeholder={currentConfig ? '••••••••' : 'Parolni kiriting'} autoComplete="new-password"
              className={errors.password ? 'input-field-error' : 'input-field'} />
            {errors.password && <p className="text-status-danger text-xs mt-1.5">{errors.password}</p>}
          </div>

          {testStatus !== 'idle' && (
            <div className={`p-3 rounded-lg border flex items-center gap-2.5 animate-slide-up ${testStatus === 'success' ? 'bg-status-successBg border-status-success/30' : testStatus === 'error' ? 'bg-status-dangerBg border-status-danger/30' : 'bg-status-warningBg border-status-warning/30'}`}>
              {testStatus === 'testing' && <Loader2 className="w-4 h-4 text-status-warning animate-spin flex-shrink-0" />}
              {testStatus === 'success' && <CheckCircle2 className="w-4 h-4 text-status-success flex-shrink-0" />}
              {testStatus === 'error' && <AlertCircle className="w-4 h-4 text-status-danger flex-shrink-0" />}
              <span className={`text-sm ${testStatus === 'success' ? 'text-status-success' : testStatus === 'error' ? 'text-status-danger' : 'text-status-warning'}`}>{testMessage}</span>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button type="submit" disabled={saving} className="btn-primary flex items-center gap-2">
              {saving ? (<><Loader2 className="w-4 h-4 animate-spin" />{t.set_saving}</>) : (<><Save className="w-4 h-4" />{t.set_save}</>)}
            </button>
            <button type="button" onClick={handleTestConnection} disabled={testStatus === 'testing'} className="btn-secondary flex items-center gap-2">
              {testStatus === 'testing' ? (<><Loader2 className="w-4 h-4 animate-spin" />{t.set_testing}</>) : (<><Zap className="w-4 h-4" />{t.set_test}</>)}
            </button>
          </div>
        </form>
      </div>

      {/* Dashboard Security Section */}
      <div className="card mt-6 border-status-danger/20">
        <div className="mb-6">
          <h3 className="section-heading flex items-center gap-2 text-status-danger">
            <Lock className="w-4 h-4" />{t.set_dash_sec_title || 'Tizim Xavfsizligi'}
          </h3>
          <p className="text-xs text-fg-muted mt-1">{t.set_dash_sec_sub || 'Dashboard paneliga kirish parolini o\'zgartirish (admin uchun)'}</p>
        </div>

        <form onSubmit={handleUpdateDashboardPassword} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="current-pass" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">
                {t.set_dash_curr_pass || 'Joriy Parol'}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-muted pointer-events-none" />
                <input id="current-pass" type="password" value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="input-field pl-10" required />
              </div>
            </div>

            <div>
              <label htmlFor="new-pass" className="block text-xs font-medium text-fg-secondary mb-1.5 uppercase tracking-wide">
                {t.set_dash_new_pass || 'Yangi Parol'}
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-muted pointer-events-none" />
                <input id="new-pass" type="password" value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="input-field pl-10" minLength={6} required />
              </div>
            </div>
          </div>

          {dashPassError && <p className="text-status-danger text-xs flex items-center gap-1"><AlertCircle className="w-3 h-3" />{dashPassError}</p>}

          {dashPassStatus !== 'idle' && (
            <div className={`p-3 rounded-lg border flex items-center gap-2.5 animate-slide-up ${dashPassStatus === 'success' ? 'bg-status-successBg border-status-success/30' : dashPassStatus === 'error' ? 'bg-status-dangerBg border-status-danger/30' : 'bg-status-warningBg border-status-warning/30'}`}>
              {dashPassStatus === 'saving' && <Loader2 className="w-4 h-4 text-status-warning animate-spin flex-shrink-0" />}
              {dashPassStatus === 'success' && <CheckCircle2 className="w-4 h-4 text-status-success flex-shrink-0" />}
              {dashPassStatus === 'error' && <AlertCircle className="w-4 h-4 text-status-danger flex-shrink-0" />}
              <span className={`text-sm ${dashPassStatus === 'success' ? 'text-status-success' : dashPassStatus === 'error' ? 'text-status-danger' : 'text-status-warning'}`}>{dashPassMsg}</span>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <button type="submit" disabled={dashPassStatus === 'saving'} className="btn-primary bg-status-danger hover:bg-status-danger/90 shadow-[0_0_15px_rgba(239,68,68,0.3)] flex items-center gap-2">
              {dashPassStatus === 'saving' ? (<><Loader2 className="w-4 h-4 animate-spin" />{t.set_saving}</>) : (<><Shield className="w-4 h-4" />{t.set_dash_update_pass || 'Parolni Yangilash'}</>)}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
