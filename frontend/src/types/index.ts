// Connection status for MikroTik router
export type ConnectionStatus = 'connected' | 'disconnected' | 'connecting';

// Navigation item for sidebar
export interface NavItem {
  label: string;
  path: string;
  icon: string;
}
