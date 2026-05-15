import * as React from "react";

export interface AppShellProps {
  /** Main page content. Mounted inside <main>. */
  children: React.ReactNode;
  /** Optional top header (logo, user menu, etc.). */
  header?: React.ReactNode;
  /** Optional side nav (typically the registered-modules nav from Plan C-shell). */
  nav?: React.ReactNode;
  className?: string;
}

/**
 * Page-level layout shell. Children render in <main>; nav + header are
 * optional slots. Plan C-shell wires auth + the dynamic module nav into
 * the `nav` slot; this component is layout-only.
 */
export function AppShell({ children, header, nav, className }: AppShellProps) {
  return (
    <div className={["irx-app-shell", className].filter(Boolean).join(" ")}>
      {header != null && <header className="irx-app-shell__header">{header}</header>}
      <div className="irx-app-shell__body">
        {nav != null && <aside className="irx-app-shell__nav">{nav}</aside>}
        <main className="irx-app-shell__main">{children}</main>
      </div>
    </div>
  );
}
