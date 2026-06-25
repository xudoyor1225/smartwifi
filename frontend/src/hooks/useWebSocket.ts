import { useState, useEffect, useRef, useCallback } from 'react';

type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error' | 'fallback';

interface WebSocketMessage {
  type: string;
  data: any;
  ts: number;
}

interface UseWebSocketOptions {
  url: string;
  token?: string | null;
  onMessage?: (type: string, data: any) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  fallbackTimeout?: number;
}

export function useWebSocket({
  url,
  token,
  onMessage,
  reconnectAttempts = 5,
  reconnectInterval = 2000,
  fallbackTimeout = 5000,
}: UseWebSocketOptions) {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const fallbackTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (!token) return;
    
    // Clear any existing connection/timers
    if (wsRef.current) {
      wsRef.current.close();
    }
    
    setStatus('connecting');
    setError(null);
    
    // Set fallback timeout if connection takes too long
    fallbackTimeoutRef.current = window.setTimeout(() => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) {
        setStatus('fallback');
        if (wsRef.current) {
          wsRef.current.close();
        }
      }
    }, fallbackTimeout);

    try {
      const wsUrl = new URL(url);
      wsUrl.searchParams.append('token', token);
      
      const ws = new WebSocket(wsUrl.toString());
      wsRef.current = ws;

      ws.onopen = () => {
        if (fallbackTimeoutRef.current) {
          clearTimeout(fallbackTimeoutRef.current);
        }
        setStatus('connected');
        reconnectCountRef.current = 0;
        
        // Start ping interval (keepalive)
        pingIntervalRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
          }
        }, 30000); // 30 seconds
      };

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          
          if (msg.type === 'pong') {
            return; // Just keepalive response
          }
          
          if (onMessage) {
            onMessage(msg.type, msg.data);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message', err);
        }
      };

      ws.onclose = (event) => {
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
        }
        
        if (event.code === 1008) {
          setStatus('error');
          setError('Invalid authentication token');
          return;
        }

        if (status !== 'fallback') {
          setStatus('disconnected');
          
          // Exponential backoff reconnect
          if (reconnectCountRef.current < reconnectAttempts) {
            const delay = reconnectInterval * Math.pow(2, reconnectCountRef.current);
            reconnectCountRef.current += 1;
            setTimeout(connect, delay);
          } else {
            setStatus('fallback'); // Exhausted retries, fallback to HTTP
          }
        }
      };

      ws.onerror = () => {
        if (status !== 'fallback') {
          setStatus('error');
          setError('WebSocket connection error');
        }
      };
    } catch (err) {
      setStatus('error');
      setError('Failed to establish WebSocket connection');
    }
  }, [url, token, onMessage, reconnectAttempts, reconnectInterval, fallbackTimeout, status]);

  useEffect(() => {
    connect();
    
    return () => {
      if (fallbackTimeoutRef.current) clearTimeout(fallbackTimeoutRef.current);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [url, token]); // Re-connect only if URL or token changes

  // Manual reconnect function for UI
  const reconnect = useCallback(() => {
    reconnectCountRef.current = 0;
    connect();
  }, [connect]);

  return {
    status,
    error,
    isFallback: status === 'fallback',
    reconnect
  };
}
