"use client";

import { useEffect, useRef, useCallback, useState } from "react";

export interface SSEEvent<T = unknown> {
  type: string;
  data: T;
  id?: string;
}

export interface UseSSEOptions {
  /** URL to connect to */
  url: string;
  /** Whether to start connected (default: true) */
  enabled?: boolean;
  /** Auto-reconnect delay in ms (default: 3000, doubles on each retry up to maxDelay) */
  reconnectDelayMs?: number;
  /** Max reconnect delay in ms (default: 30000) */
  maxReconnectDelayMs?: number;
  /** Auth token getter (called on each reconnect) */
  getToken?: () => string | null | undefined;
}

export interface UseSSEReturn<T = unknown> {
  events: SSEEvent<T>[];
  lastEvent: SSEEvent<T> | null;
  /** Shorthand for `lastEvent?.data ?? null` */
  data: T | null;
  isConnected: boolean;
  isReconnecting: boolean;
  connect: () => void;
  disconnect: () => void;
  clearEvents: () => void;
}

export function useSSE<T = unknown>(
  options: UseSSEOptions | string,
  onEvent?: (event: SSEEvent<T>) => void
): UseSSEReturn<T> {
  const normalizedOptions: UseSSEOptions =
    typeof options === "string" ? { url: options } : options;
  const {
    url,
    enabled = true,
    reconnectDelayMs = 3000,
    maxReconnectDelayMs = 30_000,
    getToken,
  } = normalizedOptions;

  const [events, setEvents] = useState<SSEEvent<T>[]>([]);
  const [lastEvent, setLastEvent] = useState<SSEEvent<T> | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);

  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(reconnectDelayMs);
  const mountedRef = useRef(true);

  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    if (mountedRef.current) {
      setIsConnected(false);
      setIsReconnecting(false);
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    disconnect();

    const token = getToken?.();
    const fullUrl = token
      ? `${url}${url.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`
      : url;

    const es = new EventSource(fullUrl);
    esRef.current = es;

    es.onopen = () => {
      if (!mountedRef.current) return;
      setIsConnected(true);
      setIsReconnecting(false);
      reconnectDelayRef.current = reconnectDelayMs;
    };

    es.onmessage = (e: MessageEvent) => {
      if (!mountedRef.current) return;
      try {
        const parsed = JSON.parse(e.data as string) as SSEEvent<T>;
        setEvents((prev) => [...prev.slice(-499), parsed]);
        setLastEvent(parsed);
        onEventRef.current?.(parsed);
      } catch {
        // non-JSON message ignored
      }
    };

    es.addEventListener("ping", () => {
      // keepalive — no action needed
    });

    es.onerror = () => {
      if (!mountedRef.current) return;
      setIsConnected(false);
      es.close();
      esRef.current = null;

      // Schedule reconnect with exponential backoff
      setIsReconnecting(true);
      const delay = Math.min(reconnectDelayRef.current, maxReconnectDelayMs);
      reconnectDelayRef.current = Math.min(delay * 2, maxReconnectDelayMs);

      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current) {
          connect();
        }
      }, delay);
    };
  }, [url, disconnect, getToken, reconnectDelayMs, maxReconnectDelayMs]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  const clearEvents = useCallback(() => {
    setEvents([]);
    setLastEvent(null);
  }, []);

  return {
    events,
    lastEvent,
    isConnected,
    isReconnecting,
    connect,
    disconnect,
    clearEvents,
    /** Convenience alias for `lastEvent?.data ?? null` */
    data: lastEvent?.data ?? null,
  };
}
