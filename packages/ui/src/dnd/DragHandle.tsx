import * as React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

export interface DragHandleProps {
  id: string;
  "aria-label"?: string;
  className?: string;
}

/**
 * Minimal sortable drag handle built on dnd-kit/sortable.
 * Foundation for SP-6's no-code program builder — the builder assembles these
 * into full drag-and-drop rule/action blocks.
 * Must be rendered inside a DndContext + SortableContext.
 */
export function DragHandle({ id, "aria-label": ariaLabel = "Drag to reorder", className }: DragHandleProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });

  const style: React.CSSProperties = {
    ...(transform != null ? { transform: CSS.Transform.toString(transform) } : {}),
    ...(transition != null ? { transition } : {}),
  };

  return (
    <button
      ref={setNodeRef}
      type="button"
      aria-label={ariaLabel}
      className={["irx-drag-handle", className].filter(Boolean).join(" ")}
      style={style}
      {...attributes}
      {...listeners}
    />
  );
}
