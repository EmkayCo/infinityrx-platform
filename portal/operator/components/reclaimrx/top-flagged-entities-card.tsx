"use client";

import React from "react";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";

interface TopEntity {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  flag_count: number;
  estimated_recovery: string;
}

const topEntityColumns: ColDef<TopEntity>[] = [
  { accessorKey: "entity_name", header: "Entity", cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span> },
  { accessorKey: "entity_type", header: "Type", cell: (c) => <span className="capitalize text-slate-300">{c.getValue() as string}</span> },
  { accessorKey: "flag_count", header: "Flags", cell: (c) => <span className="text-yellow-400 font-semibold">{c.getValue() as number}</span> },
  {
    accessorKey: "estimated_recovery",
    header: "Est. Recovery",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
];

interface Props {
  entities: TopEntity[];
}

export function TopFlaggedEntitiesCard({ entities }: Props) {
  return (
    <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-300">
          Top Flagged Entities
        </h3>
        <ExportMenu onExportCsv={() => {/* export logic */}} />
      </div>
      <DataTable
        columns={topEntityColumns}
        data={entities}
        emptyTitle="No flagged entities"
        emptyDescription="No FWA flags have been detected yet."
        getRowId={(r: TopEntity) => r.entity_id}
      />
    </div>
  );
}
