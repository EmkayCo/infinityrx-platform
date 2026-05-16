import "server-only";
import type { ReactNode } from "react";
import { AppShell } from "@infinityrx/ui";
import { ModuleNav } from "./module-nav.js";
import type { NavEntry, InstanceManifestShape } from "./nav-types.js";

// Exported so consumers (e.g. portal layouts) can type wrappers without
// reaching into src/ paths directly.
export interface AppShellMountProps {
  children: ReactNode;
  /** Optional top-bar content. Passed directly to AppShell's header slot. */
  header?: ReactNode;
  /** All nav entries registered by module packages. */
  navEntries: readonly NavEntry[];
  /** Instance manifest shape read from _generated/manifest.json. */
  manifest: InstanceManifestShape;
}

/**
 * Auth-aware AppShell server component.
 *
 * Reads the authenticated user's roles (via ModuleNav → getSessionUser),
 * filters and orders nav entries per the instance manifest, and renders
 * Plan C's <AppShell> with the dynamic nav slot populated server-side.
 *
 * The nav slot is role-filtered and manifest-ordered — users only see
 * modules they have access to and that are present in this instance's build.
 */
export async function AppShellMount({
  children,
  header,
  navEntries,
  manifest,
}: AppShellMountProps): Promise<ReactNode> {
  const nav = await ModuleNav({
    entries: navEntries,
    manifestModules: manifest.modules,
  });

  return (
    <AppShell {...(header !== undefined ? { header } : {})} {...(nav != null ? { nav: nav ?? undefined } : {})}>
      {children}
    </AppShell>
  );
}
