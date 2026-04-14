export default function ShortcutsPage() {
  const shortcuts = [
    { category: "Navigation", shortcuts: [
      { keys: "⌘K", action: "Open command palette" },
      { keys: "?", action: "Show this shortcuts reference" },
      { keys: "G then D", action: "Go to Dashboard" },
      { keys: "G then B", action: "Go to Billing" },
      { keys: "G then R", action: "Go to ReclaimRx" },
      { keys: "G then P", action: "Go to Payments" },
    ]},
    { category: "Forms & Wizards", shortcuts: [
      { keys: "⌘S", action: "Save current form / draft" },
      { keys: "⌘↵", action: "Submit / approve wizard step" },
      { keys: "Esc", action: "Close modal / cancel action" },
    ]},
    { category: "Data Tables", shortcuts: [
      { keys: "↑↓", action: "Navigate table rows" },
      { keys: "↵", action: "Open selected row detail" },
      { keys: "Space", action: "Toggle row selection" },
      { keys: "Shift+Click", action: "Multi-select range" },
      { keys: "⌘A", action: "Select all visible rows" },
      { keys: "⌘E", action: "Export selected rows" },
    ]},
    { category: "Actions", shortcuts: [
      { keys: "N", action: "New / Create (context-dependent)" },
      { keys: "F", action: "Focus filter/search" },
    ]},
  ];

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Keyboard Shortcuts</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Reference sheet for all keyboard shortcuts. Press{" "}
          <kbd className="rounded border px-1 py-0.5 text-xs font-mono">?</kbd> anywhere to show this.
        </p>
      </div>

      <div className="space-y-6">
        {shortcuts.map((section) => (
          <div key={section.category}>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {section.category}
            </h2>
            <div className="rounded-lg border bg-card overflow-hidden divide-y">
              {section.shortcuts.map((shortcut) => (
                <div key={shortcut.keys} className="flex items-center justify-between px-4 py-3">
                  <span className="text-sm">{shortcut.action}</span>
                  <kbd className="rounded border bg-muted px-2 py-0.5 text-xs font-mono text-muted-foreground shrink-0 ml-4">
                    {shortcut.keys}
                  </kbd>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
