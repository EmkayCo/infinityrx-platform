"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";
import { cn } from "@shared/lib/format";
import { NAV_MODULES } from "./nav-config";

/**
 * Auto-generated breadcrumbs from the current URL path.
 * Falls back to humanized path segments when a route isn't in NAV_MODULES.
 */
export function Breadcrumbs({ className }: { className?: string }) {
  const pathname = usePathname();

  if (pathname === "/") {
    return (
      <nav aria-label="Breadcrumb" className={cn("flex items-center", className)}>
        <span className="flex items-center gap-1.5 text-sm font-medium text-ifx-gray-700">
          <Home className="h-3.5 w-3.5 text-ifx-gray-400" />
          Dashboard
        </span>
      </nav>
    );
  }

  const segments = pathname.split("/").filter(Boolean);
  const crumbs: { label: string; href: string }[] = [{ label: "Dashboard", href: "/" }];

  // Try to match top-level segment to a module label
  if (segments.length > 0) {
    const firstSegment = "/" + segments[0];
    const matchedModule = NAV_MODULES.find(
      (m) => m.href === firstSegment || m.href.startsWith(firstSegment + "/"),
    );
    if (matchedModule) {
      crumbs.push({ label: matchedModule.label, href: matchedModule.href });
    } else {
      crumbs.push({ label: humanize(segments[0]), href: firstSegment });
    }
  }

  // Subsequent segments: try to find matching leaf labels
  let acc = "";
  for (let i = 0; i < segments.length; i++) {
    acc += "/" + segments[i];
    if (i === 0) continue; // already added
    // Look up leaf label
    let label: string | null = null;
    for (const mod of NAV_MODULES) {
      const leaf = mod.children?.find((c) => c.href === acc);
      if (leaf) {
        label = leaf.label;
        break;
      }
    }
    if (!label) label = humanize(segments[i]);
    crumbs.push({ label, href: acc });
  }

  return (
    <nav aria-label="Breadcrumb" className={cn("flex items-center min-w-0", className)}>
      <ol className="flex items-center gap-1.5 text-sm min-w-0">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <li key={crumb.href} className="flex items-center gap-1.5 min-w-0">
              {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-ifx-gray-400" />}
              {isLast ? (
                <span className="font-medium text-ifx-gray-900 truncate">{crumb.label}</span>
              ) : (
                <Link
                  href={crumb.href}
                  className="text-ifx-gray-400 hover:text-ifx-blue transition-colors truncate"
                >
                  {i === 0 ? (
                    <span className="flex items-center gap-1.5">
                      <Home className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">{crumb.label}</span>
                    </span>
                  ) : (
                    crumb.label
                  )}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function humanize(segment: string): string {
  // UUID / long hex → truncate
  if (/^[0-9a-f-]{8,}$/i.test(segment)) {
    return segment.length > 10 ? segment.slice(0, 8) + "…" : segment;
  }
  return segment
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
