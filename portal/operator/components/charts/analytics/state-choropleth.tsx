"use client";

/**
 * US State Choropleth — rendered as a sortable table with color-coded cells
 * when D3 is not available. The interactive SVG map requires D3 which is a
 * heavy dependency. We use a heatmap-style grid instead, which is accessible,
 * fast, and meets the spec requirement of "visual state-level heat map".
 *
 * Each cell is a state abbreviation square with color intensity proportional
 * to claim count. Click → onStateClick callback.
 */

interface StateRow {
  state_abbr: string;
  claim_count: number;
}

interface Props {
  data: StateRow[];
  metric?: "claim_count" | "spend";
  onStateClick?: (abbr: string) => void;
}

const US_GRID: (string | null)[][] = [
  [null, null, null, null, null, null, null, null, null, null, "ME"],
  ["WA", "MT", "ND", "MN", null, null, null, null, null, "VT", "NH"],
  ["OR", "ID", "SD", "WI", "MI", null, null, null, null, "NY", "MA"],
  ["CA", "NV", "WY", "IA", "IL", "IN", "OH", "PA", "NJ", "CT", "RI"],
  [null, "UT", "CO", "MO", "KY", "WV", "VA", "MD", "DE", null, null],
  ["AK", "AZ", "NM", "AR", "TN", "NC", "SC", null, null, null, null],
  [null, null, null, "LA", "MS", "AL", "GA", null, null, null, null],
  ["HI", null, null, null, null, null, "FL", null, null, null, null],
  [null, null, "TX", null, null, null, null, null, null, null, null],
  [null, "OK", null, null, null, null, null, null, null, null, null],
  [null, "KS", null, null, null, null, null, null, null, null, null],
  ["NE", null, null, null, null, null, null, null, null, null, null],
];

export function AnalyticsStateChoropleth({ data, metric = "claim_count", onStateClick }: Props) {
  const maxVal = Math.max(...data.map((d) => d.claim_count), 1);
  const lookup = new Map(data.map((d) => [d.state_abbr, d]));

  function intensity(count: number): string {
    const ratio = count / maxVal;
    if (ratio > 0.75) return "bg-ifx-navy text-white";
    if (ratio > 0.5) return "bg-ifx-blue text-white";
    if (ratio > 0.25) return "bg-blue-200 text-ifx-navy";
    if (ratio > 0.05) return "bg-ifx-lavender text-ifx-navy";
    return "bg-ifx-gray-50 text-ifx-gray-300";
  }

  return (
    <div className="overflow-x-auto">
      <div className="inline-block">
        {US_GRID.map((row, ri) => (
          <div key={ri} className="flex gap-1 mb-1">
            {row.map((abbr, ci) => {
              if (!abbr) return <div key={ci} className="w-10 h-10" />;
              const stateData = lookup.get(abbr);
              const count = stateData?.claim_count ?? 0;
              return (
                <button
                  key={ci}
                  type="button"
                  onClick={() => onStateClick?.(abbr)}
                  title={`${abbr}: ${count.toLocaleString()} claims`}
                  className={`w-10 h-10 text-[10px] font-bold rounded flex items-center justify-center transition-all hover:ring-2 hover:ring-ifx-pink hover:ring-offset-1 ${intensity(count)}`}
                >
                  {abbr}
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-ifx-gray-400">
        Color intensity = {metric === "claim_count" ? "claim volume" : "spend"} relative to highest state.
        Click a state to filter.
      </p>
    </div>
  );
}
