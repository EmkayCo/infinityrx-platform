import "server-only";
import type { ReactNode } from "react";
import { getSessionUser } from "../auth/get-session-user.js";
import type { NavEntry } from "./nav-types.js";

interface ModuleNavProps {
  /** All possible nav entries (registered by module packages). */
  entries: readonly NavEntry[];
  /** Module IDs from the instance manifest, in manifest order. */
  manifestModules: readonly string[];
}

/**
 * Builds the side navigation for the authenticated shell.
 *
 * Steps:
 * 1. Reads the user's roles from the server session.
 * 2. Filters entries to those whose moduleId is in manifestModules
 *    (only deployed modules appear, even if registered).
 * 3. Filters by requiredRoles (empty = any authenticated user).
 * 4. Sorts by manifest order (preserves intent from deployment manifest).
 * 5. Returns a <nav> with anchor links — fully server-rendered.
 */
export async function ModuleNav({
  entries,
  manifestModules,
}: ModuleNavProps): Promise<ReactNode> {
  const user = await getSessionUser();
  if (!user) return null;

  // Build an order map from the manifest for O(1) sort.
  const orderMap = new Map(manifestModules.map((id, i) => [id, i]));

  const visible = entries
    .filter((e) => orderMap.has(e.moduleId))
    .filter((e) =>
      e.requiredRoles.length === 0 ||
      e.requiredRoles.every((r) => user.roles.includes(r))
    )
    .sort((a, b) => (orderMap.get(a.moduleId) ?? 0) - (orderMap.get(b.moduleId) ?? 0));

  if (visible.length === 0) return null;

  return (
    <nav aria-label="Module navigation">
      <ul>
        {visible.map((e) => (
          <li key={e.moduleId}>
            <a href={e.href} aria-label={e.label}>
              {e.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
