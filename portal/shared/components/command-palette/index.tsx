"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "cmdk";
import { type LucideIcon, ArrowRight, Clock, FileText } from "lucide-react";
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

// Global registry for command palette actions
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

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  recentPages?: { label: string; href: string }[];
  onNavigate?: (href: string) => void;
}

export function CommandPalette({
  open,
  onOpenChange,
  recentPages = [],
  onNavigate,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");

  const allCommands = getRegisteredCommands();
  const actionCommands = allCommands.filter((c) => !c.category || c.category === "action");
  const pageCommands = allCommands.filter((c) => c.category === "page");

  function handleSelect(handler: () => void) {
    handler();
    onOpenChange(false);
    setQuery("");
  }

  // Default page navigation entries
  const defaultPages: CommandAction[] = [
    {
      id: "nav-dashboard",
      label: "Dashboard",
      category: "page",
      icon: ArrowRight,
      handler: () => onNavigate?.("/"),
    },
    {
      id: "nav-billing",
      label: "Billing",
      category: "page",
      icon: ArrowRight,
      handler: () => onNavigate?.("/billing"),
    },
    {
      id: "nav-payments",
      label: "Payments",
      category: "page",
      icon: ArrowRight,
      handler: () => onNavigate?.("/payments"),
    },
    {
      id: "nav-reclaimrx",
      label: "ReclaimRx — Investigation Queue",
      category: "page",
      icon: ArrowRight,
      handler: () => onNavigate?.("/reclaimrx"),
    },
    {
      id: "nav-reporting",
      label: "Reporting",
      category: "page",
      icon: ArrowRight,
      handler: () => onNavigate?.("/reporting"),
    },
    {
      id: "nav-admin",
      label: "Admin — Users",
      category: "page",
      icon: ArrowRight,
      handler: () => onNavigate?.("/admin/users"),
    },
    {
      id: "nav-audit",
      label: "Admin — Audit Log",
      category: "page",
      icon: ArrowRight,
      handler: () => onNavigate?.("/admin/audit-log"),
    },
  ];

  const pages = [...pageCommands, ...defaultPages.filter((p) => !commandRegistry.has(p.id))];

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
          placeholder="Search actions, records, pages..."
          value={query}
          onValueChange={setQuery}
          className="h-12 text-sm"
          aria-label="Command palette search"
        />
      </div>
      <CommandList className="max-h-96 overflow-y-auto">
        <CommandEmpty>
          <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
            <FileText className="h-8 w-8" />
            <p>No results for &quot;{query}&quot;</p>
          </div>
        </CommandEmpty>

        {actionCommands.length > 0 && (
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
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
              <span>{page.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
      <div className="border-t px-3 py-2">
        <p className="text-xs text-muted-foreground">
          <kbd className={cn("rounded border px-1 py-0.5 text-xs font-mono")}>↑↓</kbd> navigate{" "}
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
