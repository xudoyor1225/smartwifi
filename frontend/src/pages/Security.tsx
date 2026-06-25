import { useState, useEffect } from 'react';
import { Shield, Clock, Lock, Key, Loader2, AlertCircle, Server } from 'lucide-react';
import api from '../services/api';

export default function Security() {
  // Parental Control States
  const [pcMac, setPcMac] = useState('');
  const [pcTime, setPcTime] = useState('22:00:00-07:00:00');
  const [pcDays, setPcDays] = useState('sun,mon,tue,wed,thu,fri,sat');
  const [pcSaving, setPcSaving] = useState(false);

  // WireGuard States
  const [wgName, setWgName] = useState('wg0');
  const [wgPort, setWgPort] = useState(13231);
  const [wgSaving, setWgSaving] = useState(false);

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(''), 4000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  const saveParentalControl = async () => {
    setPcSaving(true);
    setError('');
    try {
      await api.post('/mikrotik/parental-control', null, { 
          params: { mac_address: pcMac, time: pcTime, days: pcDays } 
      });
      setSuccess("Ota-ona nazorati qoidasi muvaffaqiyatli saqlandi!");
      setPcMac('');
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || "Xatolik yuz berdi");
      }
    } finally { setPcSaving(false); }
  };

  const createWgServer = async () => {
    setWgSaving(true);
    setError('');
    try {
      await api.post('/mikrotik/wireguard/server', null, { 
          params: { name: wgName, listen_port: wgPort } 
      });
      setSuccess(`WireGuard server (${wgName}) muvaffaqiyatli yaratildi!`);
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail || "Xatolik yuz berdi");
      }
    } finally { setWgSaving(false); }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-fg-primary flex items-center gap-2">
          <Shield className="w-6 h-6 text-status-success" />
          Security & VPN
        </h2>
        <p className="text-sm text-fg-muted mt-1">
          Advanced network protection, VPN tunneling, and access restrictions.
        </p>
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

      {/* WireGuard VPN */}
      <section>
        <div className="card relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-teal-500/5 z-0" />
          <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 blur-[80px] rounded-full group-hover:bg-emerald-500/20 transition-all duration-700" />
          
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
                <Server className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-fg-primary">WireGuard VPN Server</h3>
                <p className="text-sm text-fg-muted">Create a secure, next-generation VPN tunnel directly on your router.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-bg-secondary/50 p-6 rounded-xl border border-border-subtle/50 backdrop-blur-sm">
              <div>
                <label className="text-xs font-medium text-fg-secondary block mb-1.5 uppercase tracking-wide">Interface Name</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Shield className="h-4 w-4 text-fg-subtle" />
                  </div>
                  <input type="text" value={wgName} onChange={(e) => setWgName(e.target.value)}
                    className="w-full bg-bg-primary border border-border-default rounded-lg pl-10 pr-3 py-2.5 text-sm text-fg-primary focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50 outline-none transition-all" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-fg-secondary block mb-1.5 uppercase tracking-wide">Listen Port</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Key className="h-4 w-4 text-fg-subtle" />
                  </div>
                  <input type="number" value={wgPort} onChange={(e) => setWgPort(Number(e.target.value))}
                    className="w-full bg-bg-primary border border-border-default rounded-lg pl-10 pr-3 py-2.5 text-sm text-fg-primary focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50 outline-none font-mono transition-all" />
                </div>
              </div>
            </div>
            
            <div className="mt-6 flex justify-end">
              <button onClick={createWgServer} disabled={wgSaving} className="btn-primary flex items-center gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 border-none shadow-glow-emerald text-white px-6 py-2.5">
                {wgSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Key className="w-5 h-5" />} 
                <span className="font-semibold">Deploy VPN Server</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Parental Controls */}
      <section>
        <div className="card relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-rose-500/5 z-0" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-rose-500/10 blur-[80px] rounded-full group-hover:bg-rose-500/20 transition-all duration-700" />
          
          <div className="relative z-10">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-400 to-rose-600 flex items-center justify-center shadow-lg shadow-rose-500/20">
                <Clock className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-fg-primary">Parental Controls</h3>
                <p className="text-sm text-fg-muted">Automatically cut off internet access for specific devices during set hours.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 bg-bg-secondary/50 p-6 rounded-xl border border-border-subtle/50 backdrop-blur-sm">
              <div>
                <label className="text-xs font-medium text-fg-secondary block mb-1.5 uppercase tracking-wide">Target MAC Address</label>
                <input type="text" placeholder="XX:XX:XX:XX:XX:XX" value={pcMac} onChange={(e) => setPcMac(e.target.value)}
                  className="w-full bg-bg-primary border border-border-default rounded-lg px-3 py-2.5 text-sm text-fg-primary focus:border-rose-500 focus:ring-1 focus:ring-rose-500/50 outline-none font-mono transition-all" />
              </div>
              <div>
                <label className="text-xs font-medium text-fg-secondary block mb-1.5 uppercase tracking-wide">Time Window</label>
                <input type="text" value={pcTime} onChange={(e) => setPcTime(e.target.value)}
                  className="w-full bg-bg-primary border border-border-default rounded-lg px-3 py-2.5 text-sm text-fg-primary focus:border-rose-500 focus:ring-1 focus:ring-rose-500/50 outline-none font-mono transition-all" />
              </div>
              <div>
                <label className="text-xs font-medium text-fg-secondary block mb-1.5 uppercase tracking-wide">Active Days</label>
                <input type="text" value={pcDays} onChange={(e) => setPcDays(e.target.value)}
                  className="w-full bg-bg-primary border border-border-default rounded-lg px-3 py-2.5 text-sm text-fg-primary focus:border-rose-500 focus:ring-1 focus:ring-rose-500/50 outline-none transition-all" />
              </div>
            </div>
            
            <div className="mt-6 flex justify-end">
              <button onClick={saveParentalControl} disabled={pcSaving || !pcMac} className="btn-primary flex items-center gap-2 bg-gradient-to-r from-orange-500 to-rose-600 border-none shadow-glow-rose px-6 py-2.5">
                {pcSaving ? <Loader2 className="w-5 h-5 animate-spin text-white" /> : <Lock className="w-5 h-5 text-white" />} 
                <span className="font-semibold text-white">Enforce Policy</span>
              </button>
            </div>
          </div>
        </div>
      </section>

    </div>
  );
}
