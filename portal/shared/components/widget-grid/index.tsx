"use client";

import { useState, useCallback, useEffect } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  rectSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Minimize2, Maximize2 } from "lucide-react";
import { cn } from "@shared/lib/format";

export type WidgetSize = "1x1" | "2x1" | "1x2" | "2x2";

export interface WidgetConfig {
  id: string;
  size: WidgetSize;
  title?: string;
}

const SIZE_CLASSES: Record<WidgetSize, string> = {
  "1x1": "col-span-1 row-span-1",
  "2x1": "col-span-2 row-span-1",
  "1x2": "col-span-1 row-span-2",
  "2x2": "col-span-2 row-span-2",
};

const SIZE_MIN_HEIGHTS: Record<WidgetSize, string> = {
  "1x1": "min-h-[180px]",
  "2x1": "min-h-[180px]",
  "1x2": "min-h-[380px]",
  "2x2": "min-h-[380px]",
};

interface SortableWidgetProps {
  config: WidgetConfig;
  onResize: (id: string, size: WidgetSize) => void;
  children: React.ReactNode;
}

function SortableWidget({ config, onResize, children }: SortableWidgetProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: config.id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const SIZES: WidgetSize[] = ["1x1", "2x1", "1x2", "2x2"];
  const currentIdx = SIZES.indexOf(config.size);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "group relative",
        SIZE_CLASSES[config.size],
        SIZE_MIN_HEIGHTS[config.size]
      )}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder widget"
        className={cn(
          "absolute left-2 top-2 z-10 cursor-grab active:cursor-grabbing",
          "rounded p-1 text-muted-foreground/50 hover:text-muted-foreground",
          "opacity-0 group-hover:opacity-100 transition-opacity"
        )}
      >
        <GripVertical className="h-4 w-4" />
      </button>

      {/* Resize toggle */}
      <button
        aria-label={`Resize widget (currently ${config.size})`}
        onClick={() => {
          const next = SIZES[(currentIdx + 1) % SIZES.length];
          onResize(config.id, next);
        }}
        className={cn(
          "absolute right-2 top-2 z-10",
          "rounded p-1 text-muted-foreground/50 hover:text-muted-foreground",
          "opacity-0 group-hover:opacity-100 transition-opacity"
        )}
      >
        {config.size === "2x2" ? (
          <Minimize2 className="h-3.5 w-3.5" />
        ) : (
          <Maximize2 className="h-3.5 w-3.5" />
        )}
      </button>

      {children}
    </div>
  );
}

export interface DashboardGridProps {
  widgets: WidgetConfig[];
  storageKey?: string;
  onLayoutChange?: (widgets: WidgetConfig[]) => void;
  renderWidget: (config: WidgetConfig) => React.ReactNode;
  className?: string;
}

export function DashboardGrid({
  widgets: initialWidgets,
  storageKey,
  onLayoutChange,
  renderWidget,
  className,
}: DashboardGridProps) {
  const [widgets, setWidgets] = useState<WidgetConfig[]>(() => {
    if (storageKey) {
      try {
        const stored = localStorage.getItem(storageKey);
        if (stored) {
          const parsed = JSON.parse(stored) as WidgetConfig[];
          // Merge stored layout with initial widgets to add any new ones
          const storedIds = new Set(parsed.map((w) => w.id));
          const newWidgets = initialWidgets.filter((w) => !storedIds.has(w.id));
          return [...parsed, ...newWidgets];
        }
      } catch {
        // Ignore corrupt storage
      }
    }
    return initialWidgets;
  });

  // Persist layout changes
  useEffect(() => {
    if (storageKey) {
      try {
        localStorage.setItem(storageKey, JSON.stringify(widgets));
      } catch {
        // Ignore storage errors
      }
    }
    onLayoutChange?.(widgets);
  }, [widgets, storageKey, onLayoutChange]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setWidgets((prev) => {
        const oldIdx = prev.findIndex((w) => w.id === active.id);
        const newIdx = prev.findIndex((w) => w.id === over.id);
        return arrayMove(prev, oldIdx, newIdx);
      });
    }
  }, []);

  const handleResize = useCallback((id: string, size: WidgetSize) => {
    setWidgets((prev) =>
      prev.map((w) => (w.id === id ? { ...w, size } : w))
    );
  }, []);

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext items={widgets.map((w) => w.id)} strategy={rectSortingStrategy}>
        <div
          className={cn(
            "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 auto-rows-auto",
            className
          )}
        >
          {widgets.map((config) => (
            <SortableWidget
              key={config.id}
              config={config}
              onResize={handleResize}
            >
              {renderWidget(config)}
            </SortableWidget>
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}

/** Reset layout to initial configuration */
export function resetDashboardLayout(storageKey: string) {
  try {
    localStorage.removeItem(storageKey);
  } catch {
    // Ignore
  }
}
