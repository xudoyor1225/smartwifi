import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useAuth } from '../context/AuthContext';
import { useNetwork } from '../context/NetworkContext';

export default function Layout() {
  const { logout } = useAuth();
  const { routerStatus, alerts } = useNetwork();

  return (
    <div className="min-h-screen bg-bg-primary">
      <Sidebar />
      <Header
        adminName="Admin"
        connectionStatus={routerStatus.connection_status}
        unreadCount={alerts.filter((a) => a.severity === 'high').length}
        onLogout={logout}
      />

      {/* Main content area */}
      <main className="ml-60 pt-16 min-h-screen">
        <div className="p-6 max-w-[1600px] mx-auto animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
