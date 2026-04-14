import Link from "next/link";
import { cn } from "@shared/lib/format";

const SETTINGS_NAV = [
  { label: "Profile", href: "/settings/profile" },
  { label: "Notifications", href: "/settings/notifications" },
  { label: "Dashboard", href: "/settings/dashboard" },
  { label: "Keyboard Shortcuts", href: "/settings/shortcuts" },
];

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Settings</h1>
      </div>
      <div className="flex gap-6">
        <nav className="w-48 shrink-0" aria-label="Settings navigation">
          <ul className="space-y-1">
            {SETTINGS_NAV.map((item) => (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={cn(
                    "block rounded-md px-3 py-2 text-sm transition-colors",
                    "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex-1 min-w-0">{children}</div>
      </div>
    </div>
  );
}
