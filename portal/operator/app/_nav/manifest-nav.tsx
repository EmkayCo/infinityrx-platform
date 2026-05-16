// portal/operator/app/_nav/manifest-nav.tsx
// Server component: reads _generated/manifest.json at request time and renders nav items.
// Consumes modules list from the generated artifact — this is the only file in portal/
// that references _generated/ directly. All other portal code accesses modules through
// the composition layer.
import { readFileSync } from "node:fs";
import { join } from "node:path";

interface NavItem {
  label: string;
  order: number;
  routePrefix: string;
}

function loadNavEntries(): NavItem[] {
  // _generated/manifest.json is written by build-manifest.ts at pre-build time.
  // At dev time it may not exist yet — return empty array gracefully.
  const generatedPath = join(process.cwd(), "packages", "shell", "src", "_generated", "manifest.json");
  try {
    const manifest = JSON.parse(readFileSync(generatedPath, "utf8")) as { modules: string[] };
    // Derive nav labels from module names (kebab-case → Title Case).
    // Full nav metadata (icon, order) will come from generated nav.ts in a follow-on task.
    return manifest.modules.map((name, idx) => ({
      label: name
        .split("-")
        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
        .join(" "),
      order: idx,
      routePrefix: `/${name}`,
    }));
  } catch {
    // Generated file missing — dev cold start before prebuild ran.
    return [];
  }
}

export function ManifestNav() {
  const navItems = loadNavEntries().sort((a, b) => a.order - b.order);

  if (navItems.length === 0) {
    return <nav aria-label="module navigation"><p>No modules loaded.</p></nav>;
  }

  return (
    <nav aria-label="module navigation">
      <ul>
        {navItems.map((item) => (
          <li key={item.routePrefix}>
            <a href={item.routePrefix}>{item.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
