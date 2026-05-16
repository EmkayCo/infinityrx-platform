import "server-only";
import { RequireAuth, AppShellMount } from "@infinityrx/shell";
import type { NavEntry } from "@infinityrx/shell";
// Use the "./manifest" export declared in @infinityrx/shell's package.json exports map.
// @infinityrx/shell/src/_generated/... is NOT a valid import — package.json exports
// only exposes ".", "./middleware", and "./manifest". Using the export alias
// ensures correctness after dist compilation and keeps consumers out of src/.
import manifest from "@infinityrx/shell/manifest" with { type: "json" };
import type { ReactNode } from "react";

// navEntries will be populated by module packages as they register.
// Plan D wires the registration; for now the nav renders only entries
// from this array (empty = no nav until modules register).
const navEntries: NavEntry[] = [];

export default async function AuthenticatedLayout({
  children,
}: {
  children: ReactNode;
}): Promise<ReactNode> {
  return (
    <RequireAuth loginPath="/login">
      <AppShellMount navEntries={navEntries} manifest={manifest}>
        {children}
      </AppShellMount>
    </RequireAuth>
  );
}
