import { Command } from "cmdk";

export interface CommandItem {
  id: string;
  label: string;
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: CommandItem[];
  onSelect: (id: string) => void;
  placeholder?: string;
}

/**
 * Thin cmdk wrapper. Renders as a Dialog — the host portal (Plan C-shell)
 * decides when to open it (typically keyboard shortcut Cmd+K / Ctrl+K).
 * Future: group items by category, add custom empty state, module-scoped items.
 */
export function CommandPalette({
  open,
  onOpenChange,
  items,
  onSelect,
  placeholder = "Search commands…",
}: CommandPaletteProps) {
  if (!open) return null;

  return (
    <div role="dialog" aria-modal="true" className="irx-command-palette">
      <Command>
        <Command.Input placeholder={placeholder} className="irx-command-palette__input" />
        <Command.List className="irx-command-palette__list">
          <Command.Empty>No results found.</Command.Empty>
          {items.map((item) => (
            <Command.Item
              key={item.id}
              value={item.id}
              onSelect={() => {
                onSelect(item.id);
                onOpenChange(false);
              }}
              className="irx-command-palette__item"
            >
              {item.label}
            </Command.Item>
          ))}
        </Command.List>
      </Command>
    </div>
  );
}
