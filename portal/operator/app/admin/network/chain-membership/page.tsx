"use client";

import { Building2 } from "lucide-react";

export default function ChainMembershipPage() {
  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-violet-500/10 p-2">
          <Building2 className="h-5 w-5 text-violet-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Chain membership</h1>
          <p className="text-sm text-muted-foreground">
            NPI ↔ chain code memberships. Bulk CSV upload + per-row CRUD
            land in this view (Wave 41 portal expansion).
          </p>
        </div>
      </div>
      <div className="rounded-md border border-dashed bg-card/40 p-8 text-sm text-muted-foreground">
        Use the network-management admin API directly for chain membership
        edits today. UI ships in Wave 41.
      </div>
    </div>
  );
}
