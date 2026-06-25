import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in React component tree:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-bg-primary">
          <div className="card max-w-lg w-full text-center py-12">
            <div className="w-16 h-16 bg-status-dangerBg rounded-2xl flex items-center justify-center mx-auto mb-6">
              <AlertTriangle className="w-8 h-8 text-status-danger" />
            </div>
            <h2 className="text-xl font-bold text-fg-primary mb-2">Kutilmagan xatolik yuz berdi</h2>
            <p className="text-sm text-fg-muted mb-8 max-w-md mx-auto">
              Ilovada kutilmagan xatolik yuz berdi. Iltimos, sahifani yangilang yoki kuting.
            </p>
            
            {this.state.error && (
              <div className="bg-bg-tertiary rounded-lg p-4 mb-8 text-left overflow-x-auto">
                <p className="text-xs font-mono text-status-danger break-words">
                  {this.state.error.message}
                </p>
              </div>
            )}

            <button onClick={this.handleReset} className="btn-primary inline-flex items-center gap-2">
              <RefreshCw className="w-4 h-4" />
              Sahifani yangilash
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
