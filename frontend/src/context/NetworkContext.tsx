import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react';
import api from '../services/api';
import { useAuth } from './AuthContext';
import { useWebSocket } from '../hooks/useWebSocket';

// --- Types ---

export interface NetworkStats {
  download_mbps: number;
  upload_mbps: number;
  bytes_sent: number;
  bytes_recv: number;
  ping_ms: number;
  jitter_ms: number;
  local_ip: string;
  subnet: string | null;
  ai_health?: {
    score: number;
    status: string;
    issues: string[];
  };
}

export interface LocalDevice {
  ip_address: string;
  mac_address: string;
  hostname: string | null;
  manufacturer: string;
  is_self: boolean;
  is_gateway: boolean;
  is_responsive: boolean;
  bytes_total: number;
  is_blocked?: boolean;
}

export interface TrafficPoint {
  time: string;
  timestamp: number;
  download: number;
  upload: number;
}

export interface AnomalyAlert {
  id: string;
  severity: string;
  anomaly_type: string;
  description: string | null;
  detected_at: string;
}

interface RouterStatus {
  connection_status: 'connected' | 'disconnected' | 'connecting';
  ip_address: string | null;
}

const DEFAULT_STATS: NetworkStats = {
  download_mbps: 0,
  upload_mbps: 0,
  bytes_sent: 0,
  bytes_recv: 0,
  ping_ms: 0,
  jitter_ms: 0,
  local_ip: '',
  subnet: null,
};

// --- Contexts ---

interface StatsContextType {
  stats: NetworkStats;
  trafficHistory: TrafficPoint[];
  wsStatus: 'connecting' | 'connected' | 'disconnected' | 'error' | 'fallback';
}

interface DevicesContextType {
  devices: LocalDevice[];
  isInitialLoading: boolean;
  refreshDevices: () => Promise<void>;
}

interface NetworkContextType {
  alerts: AnomalyAlert[];
  routerStatus: RouterStatus;
}

const StatsContext = createContext<StatsContextType | null>(null);
const DevicesContext = createContext<DevicesContextType | null>(null);
const NetworkContext = createContext<NetworkContextType | null>(null);

// --- Provider ---

export function NetworkProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();

  // State
  const [stats, setStats] = useState<NetworkStats>(DEFAULT_STATS);
  const [trafficHistory, setTrafficHistory] = useState<TrafficPoint[]>([]);
  const [devices, setDevices] = useState<LocalDevice[]>([]);
  const [alerts, setAlerts] = useState<AnomalyAlert[]>([]);
  const [routerStatus, setRouterStatus] = useState<RouterStatus>({
    connection_status: 'disconnected',
    ip_address: null,
  });
  const [isInitialLoading, setIsInitialLoading] = useState(true);

  // Fallback refresh functions
  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/network/stats');
      updateStats(res.data);
    } catch (err) {
      console.error('[NetworkContext] Failed to fetch stats:', err);
    }
  }, []);

  const refreshDevices = useCallback(async () => {
    try {
      const res = await api.get('/network/devices');
      setDevices(res.data.devices || []);
      setIsInitialLoading(false);
    } catch (err) {
      console.error('[NetworkContext] Failed to fetch devices:', err);
    }
  }, []);

  // Shared state updater for stats
  const updateStats = (newStats: NetworkStats) => {
    setStats((prev) => ({ ...prev, ...newStats }));
    
    const now = Date.now();
    setTrafficHistory((prev) => {
      const newPoint: TrafficPoint = {
        time: new Date(now).toLocaleTimeString('uz-UZ', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
        timestamp: now,
        download: newStats.download_mbps,
        upload: newStats.upload_mbps,
      };
      return [...prev, newPoint].slice(-80);
    });
  };

  // WebSocket Integration
  const wsUrl = window.location.protocol === 'https:' 
    ? `wss://${window.location.host}/api/ws`
    : `ws://${window.location.host}/api/ws`;
    
  // If we are in dev mode using Vite proxy, use a fixed port for WS
  const wsEndpoint = import.meta.env.DEV 
    ? `ws://${window.location.hostname}:8000/api/ws` 
    : wsUrl;

  const handleWsMessage = useCallback((type: string, data: any) => {
    if (type === 'stats.update') {
      updateStats(data);
    } else if (type === 'devices.update') {
      setDevices(data.devices || []);
      setIsInitialLoading(false);
    } else if (type === 'alert.new') {
      setAlerts((prev) => [data, ...prev].slice(0, 50));
    }
  }, []);

  const { status: wsStatus, isFallback } = useWebSocket({
    url: wsEndpoint,
    token,
    onMessage: handleWsMessage,
  });

  // Fallback HTTP Polling
  useEffect(() => {
    if (!isFallback) return;

    console.warn('[NetworkProvider] WebSocket fallback active. Using HTTP polling.');
    
    // Stats polling (5s fallback)
    fetchStats();
    const statsInterval = setInterval(fetchStats, 5000);
    
    // Devices polling (30s fallback)
    refreshDevices();
    const devicesInterval = setInterval(refreshDevices, 30000);

    return () => {
      clearInterval(statsInterval);
      clearInterval(devicesInterval);
    };
  }, [isFallback, fetchStats, refreshDevices]);

  // Initial load if WS is taking time
  useEffect(() => {
    if (isInitialLoading && !isFallback) {
      refreshDevices();
    }
  }, [isInitialLoading, isFallback, refreshDevices]);

  // Alerts Polling (Alerts push via WS too, but we need initial state)
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await api.get('/analytics/anomalies?period=24h');
        setAlerts(res.data.alerts || []);
      } catch {
        // silent
      }
    };
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 60000); // 1 min fallback sync
    return () => clearInterval(interval);
  }, []);

  // Router Status Polling
  useEffect(() => {
    let notFoundCount = 0;
    let interval: ReturnType<typeof setInterval> | null = null;

    const fetchRouter = async () => {
      try {
        const res = await api.get('/settings/router');
        notFoundCount = 0;
        setRouterStatus({
          connection_status: res.data.connection_status === 'connected' ? 'connected' : 'disconnected',
          ip_address: res.data.ip_address,
        });
      } catch (err: any) {
        if (err?.response?.status === 404) {
          notFoundCount += 1;
          if (notFoundCount >= 2 && interval) {
            clearInterval(interval);
            interval = null;
          }
        }
        setRouterStatus({ connection_status: 'disconnected', ip_address: null });
      }
    };
    
    fetchRouter();
    interval = setInterval(fetchRouter, 30000);
    return () => {
      if (interval) clearInterval(interval);
    };
  }, []);

  // Memoized Context Values
  const statsValue = useMemo(() => ({
    stats,
    trafficHistory,
    wsStatus
  }), [stats, trafficHistory, wsStatus]);

  const devicesValue = useMemo(() => ({
    devices,
    isInitialLoading,
    refreshDevices
  }), [devices, isInitialLoading, refreshDevices]);

  const networkValue = useMemo(() => ({
    alerts,
    routerStatus
  }), [alerts, routerStatus]);

  return (
    <StatsContext.Provider value={statsValue}>
      <DevicesContext.Provider value={devicesValue}>
        <NetworkContext.Provider value={networkValue}>
          {children}
        </NetworkContext.Provider>
      </DevicesContext.Provider>
    </StatsContext.Provider>
  );
}

// --- Hooks ---

export function useStats(): StatsContextType {
  const ctx = useContext(StatsContext);
  if (!ctx) throw new Error('useStats must be used within NetworkProvider');
  return ctx;
}

export function useDevices(): DevicesContextType {
  const ctx = useContext(DevicesContext);
  if (!ctx) throw new Error('useDevices must be used within NetworkProvider');
  return ctx;
}

export function useNetwork(): NetworkContextType {
  const ctx = useContext(NetworkContext);
  if (!ctx) throw new Error('useNetwork must be used within NetworkProvider');
  return ctx;
}
