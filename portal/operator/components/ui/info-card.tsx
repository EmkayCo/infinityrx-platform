import { cn } from "@shared/lib/format";
import { formatValue, type ValueFormat } from "./format-value";

export interface InfoField {
  label: string;
  value: string | number | React.ReactNode | null | undefined;
  format?: ValueFormat;
  span?: 1 | 2 | 3;
  mono?: boolean;
}

interface InfoCardProps {
  title: string;
  fields: InfoField[];
  columns?: 2 | 3 | 4;
  className?: string;
  actions?: React.ReactNode;
}

const COL_CLASSES: Record<number, string> = {
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-2 lg:grid-cols-3",
  4: "sm:grid-cols-2 lg:grid-cols-4",
};

const SPAN_CLASSES: Record<number, string> = {
  1: "",
  2: "sm:col-span-2",
  3: "sm:col-span-3",
};

export function InfoCard({
  title,
  fields,
  columns = 2,
  className,
  actions,
}: InfoCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg bg-white ifx-card-shadow overflow-hidden",
        className,
      )}
    >
      <header className="flex items-center justify-between border-b border-ifx-gray-100 px-4 py-3">
        <h3 className="text-sm font-bold text-ifx-gray-900">{title}</h3>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      <div
        className={cn(
          "grid grid-cols-1 gap-4 p-4",
          COL_CLASSES[columns] ?? COL_CLASSES[2],
        )}
      >
        {fields.map((field, i) => (
          <div
            key={`${field.label}-${i}`}
            className={cn(
              "flex flex-col gap-1 min-w-0",
              SPAN_CLASSES[field.span ?? 1],
            )}
          >
            <dt className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
              {field.label}
            </dt>
            <dd
              className={cn(
                "text-sm text-ifx-gray-900 break-words",
                field.mono && "font-mono text-[13px]",
              )}
            >
              {renderFieldValue(field)}
            </dd>
          </div>
        ))}
      </div>
    </div>
  );
}

function renderFieldValue(field: InfoField): React.ReactNode {
  if (field.value === null || field.value === undefined || field.value === "") {
    return <span className="text-ifx-gray-400">—</span>;
  }
  if (
    typeof field.value === "string" ||
    typeof field.value === "number"
  ) {
    if (field.format) {
      return formatValue(field.value, field.format);
    }
    return String(field.value);
  }
  return field.value;
}
