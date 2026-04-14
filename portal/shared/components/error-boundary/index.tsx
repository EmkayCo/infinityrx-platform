"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { cn } from "@shared/lib/format";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, info: React.ErrorInfo) => void;
  className?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  retryCount: number;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  declare context: unknown;

  private autoRetryTimer: ReturnType<typeof setTimeout> | null = null;

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  constructor(props: ErrorBoundaryProps, context: any) {
    super(props, context);
    this.state = { hasError: false, error: null, retryCount: 0 };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.props.onError?.(error, info);
    this.autoRetryTimer = setTimeout(() => {
      this.handleRetry();
    }, 30_000);
  }

  componentWillUnmount() {
    if (this.autoRetryTimer) clearTimeout(this.autoRetryTimer);
  }

  handleRetry = () => {
    if (this.autoRetryTimer) clearTimeout(this.autoRetryTimer);
    this.setState((prev) => ({
      hasError: false,
      error: null,
      retryCount: prev.retryCount + 1,
    }));
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <ErrorFallback
          error={this.state.error}
          onRetry={this.handleRetry}
          className={this.props.className}
        />
      );
    }
    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error: Error | null;
  onRetry: () => void;
  className?: string;
  compact?: boolean;
}

export function ErrorFallback({ error, onRetry, className, compact }: ErrorFallbackProps) {
  const [countdown, setCountdown] = React.useState(30);

  React.useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(timer); return 0; }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  if (compact) {
    return (
      <div className={cn("flex items-center gap-2 p-2 text-sm text-destructive", className)}>
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span>Failed to load</span>
        <button
          onClick={onRetry}
          className="ml-auto flex items-center gap-1 text-xs underline hover:no-underline"
        >
          <RefreshCw className="h-3 w-3" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-6 text-center",
        className
      )}
      role="alert"
    >
      <AlertTriangle className="h-8 w-8 text-destructive" />
      <div>
        <h3 className="font-semibold text-sm text-destructive">Something went wrong</h3>
        {error && (
          <p className="mt-1 text-xs text-muted-foreground max-w-xs line-clamp-2">{error.message}</p>
        )}
      </div>
      <div className="flex gap-2">
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 rounded-md bg-destructive/10 hover:bg-destructive/20 px-3 py-1.5 text-xs font-medium text-destructive transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry now
        </button>
        <a
          href="mailto:support@infinityrx.com?subject=Portal+Error+Report"
          className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors"
        >
          Report issue
        </a>
      </div>
      {countdown > 0 && (
        <p className="text-xs text-muted-foreground">Auto-retrying in {countdown}s</p>
      )}
    </div>
  );
}

export function WidgetErrorBoundary({ children, title }: { children: React.ReactNode; title?: string }) {
  return (
    <ErrorBoundary
      fallback={
        <div className="rounded-lg border bg-card p-4 h-full min-h-[180px] flex flex-col">
          {title && <div className="text-sm font-medium text-muted-foreground mb-3">{title}</div>}
          <ErrorFallback error={null} onRetry={() => window.location.reload()} compact />
        </div>
      }
    >
      {children}
    </ErrorBoundary>
  );
}

export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  fallback?: React.ReactNode
) {
  const Wrapped = (props: P) => (
    <ErrorBoundary fallback={fallback}>
      <Component {...props} />
    </ErrorBoundary>
  );
  Wrapped.displayName = `withErrorBoundary(${Component.displayName ?? Component.name})`;
  return Wrapped;
}
