"use client";

import React, { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  DragOverlay,
  useDraggable,
  useDroppable,
  type DragEndEvent,
  type DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { AlertTriangle, Clock, DollarSign } from "lucide-react";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, apiPatch, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Investigation, InvestigationStatus, FlagSeverity } from "@shared/types/reclaimrx";
import { cn } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const COLUMNS: { id: InvestigationStatus; label: string }[] = [
  { id: "new", label: "New" },
  { id: "assigned", label: "Assigned" },
  { id: "evidence", label: "Evidence" },
  { id: "demand", label: "Demand" },
  { id: "resolved", label: "Resolved" },
];

const SEVERITY_BADGE: Record<FlagSeverity, string> = {
  critical: "bg-red-900/40 text-red-300 border-red-700/30",
  high: "bg-orange-900/40 text-orange-300 border-orange-700/30",
  medium: "bg-yellow-900/40 text-yellow-300 border-yellow-700/30",
  low: "bg-slate-700/40 text-slate-400 border-slate-600/30",
};

function InvestigationCard({
  investigation,
  isDragging,
}: {
  investigation: Investigation;
  isDragging?: boolean;
}) {
  const router = useRouter();
  const { flag } = investigation;

  return (
    <div
      className={cn(
        "p-3 rounded-lg border bg-navy-900 cursor-pointer",
        "border-ifx-border-dark hover:border-teal-600/40 transition-colors",
        isDragging && "opacity-50 shadow-2xl"
      )}
      onClick={() => router.push(`/reclaimrx/investigations/${investigation.id}`)}
    >
      <div className="flex items-start justify-between mb-2">
        <span
          className={cn(
            "text-xs px-2 py-0.5 rounded border capitalize",
            SEVERITY_BADGE[flag.severity]
          )}
        >
          {flag.severity}
        </span>
        <span className="text-xs text-slate-500 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          {investigation.days_open}d
        </span>
      </div>
      <p className="text-sm font-medium text-white leading-snug mb-1 truncate">
        {flag.entity_name}
      </p>
      <p className="text-xs text-slate-400 capitalize mb-2">
        {flag.flag_type.replace(/_/g, " ")}
      </p>
      <div className="flex items-center gap-1 text-xs text-slate-400">
        <DollarSign className="w-3 h-3" />
        <DollarDisplay amount={investigation.estimated_recovery} size="sm" showScale={false} />
      </div>
      {investigation.assigned_to_name && (
        <p className="text-xs text-slate-500 mt-1.5 truncate">
          → {investigation.assigned_to_name}
        </p>
      )}
    </div>
  );
}

function DraggableCard({ investigation }: { investigation: Investigation }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: investigation.id,
    data: { investigation },
  });

  const style = transform
    ? { transform: CSS.Translate.toString(transform) }
    : undefined;

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <InvestigationCard investigation={investigation} isDragging={isDragging} />
    </div>
  );
}

function KanbanColumn({
  status,
  label,
  investigations,
}: {
  status: InvestigationStatus;
  label: string;
  investigations: Investigation[];
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });

  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex flex-col flex-1 min-w-[220px] rounded-xl border",
        "border-ifx-border-dark bg-navy-900/40 transition-colors",
        isOver && "border-teal-600/60 bg-teal-900/10"
      )}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-ifx-border-dark">
        <h3 className="text-sm font-semibold text-slate-200">{label}</h3>
        <span className="text-xs bg-navy-700 text-slate-400 px-2 py-0.5 rounded-full">
          {investigations.length}
        </span>
      </div>
      <div className="flex-1 p-3 space-y-2 overflow-y-auto max-h-[calc(100vh-280px)]">
        {investigations.map((inv) => (
          <DraggableCard key={inv.id} investigation={inv} />
        ))}
        {investigations.length === 0 && (
          <p className="text-xs text-slate-600 text-center py-8">No items</p>
        )}
      </div>
    </div>
  );
}

export function InvestigationsKanban() {
  const queryClient = useQueryClient();
  const [activeInv, setActiveInv] = useState<Investigation | null>(null);

  const { data: investigations = [], isLoading } = useQuery<Investigation[]>({
    queryKey: ["investigations"],
    queryFn: () =>
      apiGet<Investigation[]>(buildUrl(`${API_URLS.reclaimrx}/api/v1/investigations`)),
    staleTime: 30_000,
  });

  const updateStatus = useMutation({
    mutationFn: ({
      id,
      status,
    }: {
      id: string;
      status: InvestigationStatus;
    }) =>
      apiPatch(`${API_URLS.reclaimrx}/api/v1/investigations/${id}`, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["investigations"] });
    },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const handleDragStart = useCallback(
    (event: DragStartEvent) => {
      const inv = investigations.find((i) => i.id === event.active.id);
      setActiveInv(inv ?? null);
    },
    [investigations]
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveInv(null);
      const { active, over } = event;
      if (!over || active.id === over.id) return;
      const targetStatus = over.id as InvestigationStatus;
      const validStatuses = COLUMNS.map((c) => c.id);
      if (!validStatuses.includes(targetStatus)) return;
      const inv = investigations.find((i) => i.id === active.id);
      if (inv && inv.status !== targetStatus) {
        updateStatus.mutate({ id: String(active.id), status: targetStatus });
      }
    },
    [investigations, updateStatus]
  );

  const grouped = COLUMNS.reduce(
    (acc, col) => {
      acc[col.id] = investigations.filter((i) => i.status === col.id);
      return acc;
    },
    {} as Record<InvestigationStatus, Investigation[]>
  );

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-4">
          {COLUMNS.map((c) => (
            <Skeleton key={c.id} className="flex-1 h-96 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 flex flex-col gap-4 h-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Investigation Queue</h1>
          <p className="text-slate-400 text-sm mt-1">
            {investigations.length} active investigations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-orange-400" />
          <span className="text-sm text-slate-400">
            Drag cards to update status
          </span>
        </div>
      </div>

      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="flex gap-4 overflow-x-auto pb-2">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col.id}
              status={col.id}
              label={col.label}
              investigations={grouped[col.id] ?? []}
            />
          ))}
        </div>
        <DragOverlay>
          {activeInv && (
            <InvestigationCard investigation={activeInv} isDragging />
          )}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
