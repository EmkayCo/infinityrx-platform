"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Building2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listPayToEntities, type PayToEntity, type PayToListQuery, type EntityType,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";
import { StatusBadge } from "@/components/ui/status-badge";

export default function PayToEntitiesPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "name", sort_dir: "asc",
  }), [params]);

  const entityType = (params.get("entity_type") as EntityType | null) ?? undefined;
  const status = params.get("status") ?? undefined;
  const hasBanking = params.get("has_banking") === "true" ? true
    : params.get("has_banking") === "false" ? false : undefined;
  const search = params.get("search") ?? undefined;

  const [rows, setRows] = useState<PayToEntity[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const q: PayToListQuery = {
      ...pagination, entity_type: entityType, status, has_banking: hasBanking, search,
    };
    listPayToEntities(q)
      .then((p) => { if (!cancelled) { setRows(p.items); setTotal(p.total); } })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        if (!cancelled) { setError(msg); toast.error(`Failed to load pay-to entities — ${msg}`); }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pagination, entityType, status, hasBanking, search]);

  const columns: PaginatedColumn<PayToEntity>[] = [
    {
      id: "external_id", header: "ID", sortKey: "external_id",
      accessor: (row) => (
        <Link href={`/admin/network/pay-to-entities/${row.id}`}
              className="font-mono text-sky-500 hover:underline">
          {row.external_id}
        </Link>
      ),
    },
    {
      id: "name", header: "Name", sortKey: "name",
      accessor: (row) => row.name,
    },
    {
      id: "type", header: "Type", sortKey: "entity_type",
      accessor: (row) => <span className="text-xs">{row.entity_type}</span>,
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => <StatusBadge status={row.status.replace(/_/g, " ")} />,
    },
    {
      id: "banking", header: "Banking",
      accessor: (row) => row.has_active_banking
        ? <span className="text-xs text-emerald-500">configured</span>
        : <span className="text-xs text-amber-500">missing</span>,
    },
    {
      id: "contracts", header: "Contracts", align: "right",
      accessor: (row) => row.contract_count,
    },
    {
      id: "effective_from", header: "Effective from", sortKey: "effective_from",
      accessor: (row) => <span className="font-mono text-xs">{row.effective_from}</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-violet-500/10 p-2">
          <Building2 className="h-5 w-5 text-violet-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Pay-to entities</h1>
          <p className="text-sm text-muted-foreground">
            Network destinations: pharmacies, chains, pay centers,
            manufacturers, clients. Banking + contracts + routing live
            inside the entity detail.
          </p>
        </div>
      </div>

      <PaginatedTable<PayToEntity>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(p) => p.id}
        emptyTitle="No pay-to entities match the filters"
      />
    </div>
  );
}
