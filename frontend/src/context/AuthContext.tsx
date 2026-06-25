import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from 'react';
import { useNavigate } from 'react-router-dom';
import api, {
  getStoredToken,
  setStoredToken,
  setUnauthorizedHandler,
} from '../services/api';

interface AuthContextType {
  isAuthenticated: boolean;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  sessionExpired: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const SESSION_DURATION_MS = 30 * 60 * 1000; // 30 minutes

export function AuthProvider({ children }: { children: ReactNode }) {
  // Hydrate token from localStorage on mount - allows page reload without re-login
  const [token, setTokenState] = useState<string | null>(() => getStoredToken());
  const [sessionExpired, setSessionExpired] = useState(false);
  const navigate = useNavigate();
  const expiryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isAuthenticated = token !== null;

  // Persist token changes to localStorage
  const setToken = useCallback((newToken: string | null) => {
    setStoredToken(newToken);
    setTokenState(newToken);
  }, []);

  const clearExpiryTimer = useCallback(() => {
    if (expiryTimerRef.current) {
      clearTimeout(expiryTimerRef.current);
      expiryTimerRef.current = null;
    }
  }, []);

  const handleSessionExpiry = useCallback(() => {
    clearExpiryTimer();
    setToken(null);
    setSessionExpired(true);
    navigate('/login');
  }, [clearExpiryTimer, navigate, setToken]);

  const startExpiryTimer = useCallback(() => {
    clearExpiryTimer();
    expiryTimerRef.current = setTimeout(() => {
      handleSessionExpiry();
    }, SESSION_DURATION_MS);
  }, [clearExpiryTimer, handleSessionExpiry]);

  // Register unauthorized handler with API service (once)
  useEffect(() => {
    setUnauthorizedHandler(() => handleSessionExpiry());
  }, [handleSessionExpiry]);

  // Start expiry timer if user is already authenticated on mount
  useEffect(() => {
    if (token) {
      startExpiryTimer();
    }
    return () => clearExpiryTimer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (username: string, password: string) => {
      setSessionExpired(false);
      const response = await api.post('/auth/login', { username, password });
      const { access_token } = response.data;
      setToken(access_token);
      startExpiryTimer();
    },
    [startExpiryTimer, setToken]
  );

  const logout = useCallback(() => {
    clearExpiryTimer();
    setToken(null);
    setSessionExpired(false);
    navigate('/login');
  }, [clearExpiryTimer, navigate, setToken]);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, token, login, logout, sessionExpired }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
