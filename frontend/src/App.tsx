import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { NetworkProvider } from './context/NetworkContext';
import { LanguageProvider } from './context/LanguageContext';
import { ThemeProvider } from './context/ThemeContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './context/ToastContext';

// Lazy load pages for Code Splitting optimization
const Login = lazy(() => import('./pages/Login'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Devices = lazy(() => import('./pages/Devices'));
const Restrictions = lazy(() => import('./pages/Restrictions'));
const Analytics = lazy(() => import('./pages/Analytics'));
const NetworkMap = lazy(() => import('./pages/NetworkMap'));
const Security = lazy(() => import('./pages/Security'));
const Settings = lazy(() => import('./pages/Settings'));

// Loading fallback component
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen bg-[#0F1623]">
    <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
  </div>
);

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
      <LanguageProvider>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route
                  path="/"
                  element={
                    <ProtectedRoute>
                      <NetworkProvider>
                        <Layout />
                      </NetworkProvider>
                    </ProtectedRoute>
                  }
                >
                  <Route index element={<Dashboard />} />
                  <Route path="devices" element={<Devices />} />
                  <Route path="restrictions" element={<Restrictions />} />
                  <Route path="analytics" element={<Analytics />} />
                  <Route path="network-map" element={<NetworkMap />} />
                  <Route path="security" element={<Security />} />
                  <Route path="settings" element={<Settings />} />
                </Route>
              </Routes>
            </Suspense>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
      </LanguageProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
