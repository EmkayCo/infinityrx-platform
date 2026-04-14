"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { isMockEnabled } from "@shared/lib/mock-data";

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

    if (isMockEnabled()) {
      // Mock mode: simulate SSE with a rotating set of stub events via setInterval
      const MOCK_EVENTS: SSEEvent<unknown>[] = [
        { type: "activity", data: { action: "billing_cycle_approved", user: "Sarah Chen", module: "billing", description: "Billing cycle approved — $2.8M AP", occurred_at: new Date().toISOString() } },
        { type: "activity", data: { action: "fwa_flag_created", user: "System", module: "reclaimrx", description: "High-severity flag detected at QuickScript Pharmacy", occurred_at: new Date().toISOString() } },
        { type: "activity", data: { action: "payment_batch_transmitted", user: "Marcus Rivera", module: "payments", description: "NACHA batch transmitted — 847 payments", occurred_at: new Date().toISOString() } },
        { type: "activity", data: { action: "edi_transaction_accepted", user: "System", module: "edi", description: "835 remittance accepted from BlueCross", occurred_at: new Date().toISOString() } },
        { type: "metrics", data: { claims_per_hour: 2847, dollars_flowing: "1423891.20", flags_per_day: 34, as_of: new Date().toISOString() } },
        { type: "activity", data: { action: "report_generated", user: "System", module: "reporting", description: "Monthly Billing Summary ready", occurred_at: new Date().toISOString() } },
      ];
      let eventIndex = 0;

      setIsConnected(true);

      const intervalId = setInterval(() => {
        if (!mountedRef.current) return;
        const evt = { ...MOCK_EVENTS[eventIndex % MOCK_EVENTS.length], id: String(Date.now()) } as SSEEvent<T>;
        setEvents((prev) => [...prev.slice(-499), evt]);
        setLastEvent(evt);
        onEventRef.current?.(evt);
        eventIndex += 1;
      }, 4000 + Math.floor(Math.random() * 4000));

      return () => {
        mountedRef.current = false;
        clearInterval(intervalId);
        setIsConnected(false);
      };
    }

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
