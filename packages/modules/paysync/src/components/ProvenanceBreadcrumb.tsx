// packages/modules/paysync/src/components/ProvenanceBreadcrumb.tsx
// Renders a provenance chain (upload → cycle → batch → payment, etc).
// Truncates middle items when chain >4 nodes; shows first + last 2 with "...".

import type { ReactElement } from "react";

export interface ProvenanceLink {
  readonly label: string;
  readonly href: string;
}

export interface ProvenanceBreadcrumbProps {
  readonly chain: ReadonlyArray<ProvenanceLink>;
}

const TRUNCATION_THRESHOLD = 4;

export function ProvenanceBreadcrumb({ chain }: ProvenanceBreadcrumbProps): ReactElement {
  let visible: ReadonlyArray<ProvenanceLink | null>;
  if (chain.length > TRUNCATION_THRESHOLD) {
    // first + null sentinel for "..." + last 2
    visible = [chain[0]!, null, chain[chain.length - 2]!, chain[chain.length - 1]!];
  } else {
    visible = chain;
  }

  return (
    <nav aria-label="Provenance" data-testid="provenance-breadcrumb">
      {visible.map((link, index) => (
        <span key={link === null ? `truncated-${index}` : `${link.href}-${index}`}>
          {link === null ? (
            <span data-testid="provenance-truncated">…</span>
          ) : (
            <a href={link.href} data-testid={`provenance-link-${index}`}>
              {link.label}
            </a>
          )}
          {index < visible.length - 1 && <span aria-hidden="true"> / </span>}
        </span>
      ))}
    </nav>
  );
}
