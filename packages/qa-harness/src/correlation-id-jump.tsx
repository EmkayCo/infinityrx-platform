import * as React from "react";

export interface CorrelationIdJumpProps {
  /**
   * Base URL of the log-search route. The correlation id is appended as
   * a `q` query param: `{logSearchBaseUrl}?q={correlationId}`.
   * Example: "https://logs.example.com/search"
   */
  logSearchBaseUrl: string;
  className?: string;
}

/**
 * Dev tool: paste a correlation_id to copy it to clipboard and open the
 * matching backend log entry in one click.
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function CorrelationIdJump({ logSearchBaseUrl, className }: CorrelationIdJumpProps) {
  const [correlationId, setCorrelationId] = React.useState("");

  const logUrl = correlationId.trim()
    ? `${logSearchBaseUrl}?q=${encodeURIComponent(correlationId.trim())}`
    : null;

  async function handleCopy() {
    if (correlationId.trim()) {
      await navigator.clipboard.writeText(correlationId.trim());
    }
  }

  return (
    <div className={["irx-qa-correlation-jump", className].filter(Boolean).join(" ")}>
      <label htmlFor="irx-correlation-input" className="irx-qa-correlation-jump__label">
        Correlation ID
      </label>
      <div className="irx-qa-correlation-jump__row">
        <input
          id="irx-correlation-input"
          type="text"
          className="irx-qa-correlation-jump__input"
          value={correlationId}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCorrelationId(e.target.value)}
          placeholder="Paste correlation_id…"
        />
        <button
          type="button"
          aria-label="Copy correlation id to clipboard"
          className="irx-qa-correlation-jump__copy"
          onClick={() => void handleCopy()}
        >
          Copy
        </button>
        {logUrl != null && (
          <a
            href={logUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="irx-qa-correlation-jump__link"
          >
            Open in logs
          </a>
        )}
      </div>
    </div>
  );
}
