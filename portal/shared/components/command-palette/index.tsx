"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "cmdk";
import {
  type LucideIcon,
  ArrowRight,
  Clock,
  FileText,
  Receipt,
  Building2,
  Stethoscope,
  User as UserIcon,
  ShieldAlert,
  FileBarChart,
} from "lucide-react";
import { cn } from "@shared/lib/format";

export interface CommandAction {
  id: string;
  label: string;
  description?: string;
  category?: string;
  icon?: LucideIcon;
  handler: () => void;
  keywords?: string[];
}

const commandRegistry = new Map<string, CommandAction>();

export function registerCommand(action: CommandAction): void {
  commandRegistry.set(action.id, action);
}

export function unregisterCommand(id: string): void {
  commandRegistry.delete(id);
}

export function getRegisteredCommands(): CommandAction[] {
  return Array.from(commandRegistry.values());
}

export type EntityKind =
  | "claim"
  | "pharmacy"
  | "prescriber"
  | "member"
  | "investigation"
  | "invoice";

export interface EntitySearchResult {
  id: string;
  kind: EntityKind;
  primary: string;
  secondary?: string;
  href: string;
}

export type EntitySearchFn = (
  query: string,
) => Promise<EntitySearchResult[]> | EntitySearchResult[];

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recentPages?: { label: string; href: string }[];
  onNavigate?: (href: string) => void;
  entitySearch?: EntitySearchFn;
}

const ENTITY_ICONS: Record<EntityKind, LucideIcon> = {
  claim: FileText,
  pharmacy: Building2,
  prescriber: Stethoscope,
  member: UserIcon,
  investigation: ShieldAlert,
  invoice: Receipt,
};

const ENTITY_LABELS: Record<EntityKind, string> = {
  claim: "Claims",
  pharmacy: "Pharmacies",
  prescriber: "Prescribers",
  member: "Members",
  investigation: "Investigations",
  invoice: "Invoices",
};

export function CommandPalette({
  open,
  onOpenChange,
  recentPages = [],
  onNavigate,
  entitySearch,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [entityResults, setEntityResults] = useState<EntitySearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Debounce the query for entity search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // Run entity search when debounced query changes
  useEffect(() => {
    if (!entitySearch || !debouncedQuery || debouncedQuery.trim().length < 2) {
      setEntityResults([]);
      return;
    }
    let cancelled = false;
    setSearching(true);
    Promise.resolve(entitySearch(debouncedQuery))
      .then((results) => {
        if (!cancelled) setEntityResults(results);
      })
      .catch(() => {
        if (!cancelled) setEntityResults([]);
      })
      .finally(() => {
        if (!cancelled) setSearching(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, entitySearch]);

  const allCommands = getRegisteredCommands();
  const actionCommands = allCommands.filter(
    (c) => !c.category || c.category === "action",
  );
  const pageCommands = allCommands.filter((c) => c.category === "page");

  function handleSelect(handler: () => void) {
    handler();
    onOpenChange(false);
    setQuery("");
  }

  // Default page navigation entries — ICP Operator Portal modules
  const defaultPages: CommandAction[] = useMemo(
    () => [
      { id: "nav-dashboard", label: "Dashboard", category: "page", icon: ArrowRight, handler: () => onNavigate?.("/") },
      { id: "nav-claims", label: "Claims Explorer", category: "page", icon: FileText, handler: () => onNavigate?.("/claims") },
      { id: "nav-reclaimrx", label: "ReclaimRx — GTN Dashboard", category: "page", icon: ShieldAlert, handler: () => onNavigate?.("/reclaimrx") },
      { id: "nav-investigations", label: "Investigations", category: "page", icon: ShieldAlert, handler: () => onNavigate?.("/reclaimrx/investigations") },
      { id: "nav-accounting", label: "Accounting — Billing Cycles", category: "page", icon: Receipt, handler: () => onNavigate?.("/accounting/cycles") },
      { id: "nav-invoices", label: "Invoices", category: "page", icon: Receipt, handler: () => onNavigate?.("/accounting/invoices") },
      { id: "nav-pharmacies", label: "Pharmacies Directory", category: "page", icon: Building2, handler: () => onNavigate?.("/directories/pharmacies") },
      { id: "nav-reporting", label: "Report Library", category: "page", icon: FileBarChart, handler: () => onNavigate?.("/reporting/library") },
      { id: "nav-admin-users", label: "Admin — Users & Roles", category: "page", icon: ArrowRight, handler: () => onNavigate?.("/admin/users") },
      { id: "nav-admin-audit", label: "Admin — Audit Log", category: "page", icon: ArrowRight, handler: () => onNavigate?.("/admin/audit-log") },
    ],
    [onNavigate],
  );

  const pages = [...pageCommands, ...defaultPages.filter((p) => !commandRegistry.has(p.id))];

  // Group entity results by kind, preserving discovery order
  const groupedResults: Record<EntityKind, EntitySearchResult[]> = {
    claim: [],
    pharmacy: [],
    prescriber: [],
    member: [],
    investigation: [],
    invoice: [],
  };
  for (const r of entityResults) {
    groupedResults[r.kind].push(r);
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (!o) setQuery("");
      }}
    >
      <div className="border-b">
        <CommandInput
          placeholder="Search claims, pharmacies, prescribers, members, investigations..."
          value={query}
          onValueChange={setQuery}
          className="h-12 text-sm"
          aria-label="Command palette search"
        />
      </div>
      <CommandList className="max-h-[28rem] overflow-y-auto">
        <CommandEmpty>
          <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
            <FileText className="h-8 w-8" />
            <p>No results for &quot;{query}&quot;</p>
          </div>
        </CommandEmpty>

        {searching && (
          <div className="px-3 py-2 text-xs text-muted-foreground">Searching…</div>
        )}

        {/* Entity results grouped by kind */}
        {(Object.keys(groupedResults) as EntityKind[]).map((kind) => {
          const results = groupedResults[kind];
          if (results.length === 0) return null;
          const Icon = ENTITY_ICONS[kind];
          return (
            <CommandGroup key={kind} heading={ENTITY_LABELS[kind]}>
              {results.map((r) => (
                <CommandItem
                  key={`${r.kind}-${r.id}`}
                  value={`${r.primary} ${r.secondary ?? ""} ${r.id}`}
                  onSelect={() => handleSelect(() => onNavigate?.(r.href))}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <div className="flex flex-col min-w-0">
                    <span className="truncate">{r.primary}</span>
                    {r.secondary && (
                      <span className="text-xs text-muted-foreground truncate">
                        {r.secondary}
                      </span>
                    )}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          );
        })}

        {actionCommands.length > 0 && (
          <>
            {entityResults.length > 0 && <CommandSeparator />}
            <CommandGroup heading="Actions">
              {actionCommands.map((action) => (
                <CommandItem
                  key={action.id}
                  value={`${action.label} ${action.keywords?.join(" ") ?? ""}`}
                  onSelect={() => handleSelect(action.handler)}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  {action.icon ? (
                    <action.icon className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <span className="h-4 w-4" />
                  )}
                  <span>{action.label}</span>
                  {action.description && (
                    <span className="ml-auto text-xs text-muted-foreground">
                      {action.description}
                    </span>
                  )}
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        {recentPages.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Recent">
              {recentPages.map((page) => (
                <CommandItem
                  key={page.href}
                  value={page.label}
                  onSelect={() => handleSelect(() => onNavigate?.(page.href))}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span>{page.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}

        <CommandSeparator />
        <CommandGroup heading="Pages">
          {pages.map((page) => (
            <CommandItem
              key={page.id}
              value={page.label}
              onSelect={() => handleSelect(page.handler)}
              className="flex items-center gap-2 cursor-pointer"
            >
              {page.icon ? (
                <page.icon className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ArrowRight className="h-4 w-4 text-muted-foreground" />
              )}
              <span>{page.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
      <div className="border-t px-3 py-2">
        <p className="text-xs text-muted-foreground">
          <kbd className={cn("rounded border px-1 py-0.5 text-xs font-mono")}>↑↓</kbd>{" "}
          navigate{" "}
          <kbd className="rounded border px-1 py-0.5 text-xs font-mono">↵</kbd> select{" "}
          <kbd className="rounded border px-1 py-0.5 text-xs font-mono">esc</kbd> close
        </p>
      </div>
    </CommandDialog>
  );
}

/** Hook to control command palette open state */
export function useCommandPalette() {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => setOpen((o) => !o), []);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        toggle();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggle]);

  return { open, setOpen, toggle };
}
