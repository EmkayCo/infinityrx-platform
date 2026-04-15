import { cn } from "@shared/lib/format";
import { KpiCard, type KpiCardProps } from "./kpi-card";

interface KpiCardRowProps {
  cards: KpiCardProps[];
  columns?: 2 | 3 | 4 | 5 | 6;
  className?: string;
}

const COL_CLASSES: Record<number, string> = {
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-2 lg:grid-cols-3",
  4: "sm:grid-cols-2 lg:grid-cols-4",
  5: "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5",
  6: "sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6",
};

export function KpiCardRow({ cards, columns, className }: KpiCardRowProps) {
  const cols = columns ?? Math.min(6, Math.max(2, cards.length)) as 2 | 3 | 4 | 5 | 6;
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-3",
        COL_CLASSES[cols] ?? COL_CLASSES[4],
        className,
      )}
    >
      {cards.map((card, i) => (
        <KpiCard key={`${card.label}-${i}`} {...card} />
      ))}
    </div>
  );
}
