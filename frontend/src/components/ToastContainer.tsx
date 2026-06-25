import { AlertCircle, CheckCircle, Info, XCircle, X } from 'lucide-react';
import type { Toast } from '../context/ToastContext';

interface ToastContainerProps {
  toasts: Toast[];
  removeToast: (id: string) => void;
}

export default function ToastContainer({ toasts, removeToast }: ToastContainerProps) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md w-full">
      {toasts.map((toast) => {
        const Icon = 
          toast.type === 'success' ? CheckCircle :
          toast.type === 'error' ? XCircle :
          toast.type === 'warning' ? AlertCircle : Info;
          
        const colorClass = 
          toast.type === 'success' ? 'text-status-success' :
          toast.type === 'error' ? 'text-status-danger' :
          toast.type === 'warning' ? 'text-status-warning' : 'text-status-info';
          
        const bgClass = 'bg-bg-secondary border border-border-subtle shadow-xl';

        return (
          <div
            key={toast.id}
            className={`p-4 rounded-xl flex items-start gap-3 animate-slide-up ${bgClass}`}
          >
            <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${colorClass}`} />
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-fg-primary">{toast.title}</h4>
              {toast.message && (
                <p className="text-sm text-fg-muted mt-1 break-words">{toast.message}</p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="p-1 rounded-md text-fg-muted hover:text-fg-primary hover:bg-bg-hover transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
