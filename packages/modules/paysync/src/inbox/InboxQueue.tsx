// packages/modules/paysync/src/inbox/InboxQueue.tsx
// Virtualized inbox list filtered by role. Renders each item via the
// kind-keyed ItemRegistry. Plan B replaces the placeholder card factories
// with real cards in ItemRegistry (Task 5); InboxQueue itself stays stable.

import { useMemo, useRef, useState, useEffect, type ReactElement } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { InboxItem, RbacRole } from "./types.js";
import { ItemRegistry, type InboxCardComponent } from "./ItemRegistry.js";

export interface InboxQueueProps {
  readonly items: ReadonlyArray<InboxItem>;
  readonly role: RbacRole;
}

const ROW_HEIGHT_PX = 72;

export function InboxQueue({ items, role }: InboxQueueProps): ReactElement {
  const filtered = useMemo(
    () => items.filter((item) => item.rbac_required === role),
    [items, role],
  );

  const parentRef = useRef<HTMLDivElement | null>(null);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT_PX,
    overscan: 4,
  });

  if (filtered.length === 0) {
    return (
      <div data-testid="inbox-queue-empty" role="status">
        No items in inbox.
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      data-testid="inbox-queue"
      role="list"
      style={{ height: "100%", overflow: "auto" }}
    >
      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: "relative" }}>
        {virtualizer.getVirtualItems().map((vrow) => {
          const item = filtered[vrow.index];
          if (item === undefined) return null;
          return (
            <div
              key={item.id}
              role="listitem"
              data-testid={`inbox-row-${item.kind}`}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: `${vrow.size}px`,
                transform: `translateY(${vrow.start}px)`,
              }}
            >
              <InboxCard item={item} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function InboxCard({ item }: { readonly item: InboxItem }): ReactElement {
  const [Card, setCard] = useState<InboxCardComponent | null>(null);

  useEffect(() => {
    let cancelled = false;
    ItemRegistry[item.kind].card().then((mod) => {
      if (!cancelled) setCard(() => mod.default);
    }).catch(() => {
      // Surface failure deterministically; production telemetry not in scope for Plan A.
      if (!cancelled) setCard(null);
    });
    return () => {
      cancelled = true;
    };
  }, [item.kind]);

  if (Card === null) {
    return <div data-testid={`inbox-card-loading-${item.kind}`}>Loading {item.kind}…</div>;
  }
  return <Card item={item} />;
}
