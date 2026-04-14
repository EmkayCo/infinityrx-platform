"use client";

/**
 * DemoBanner — a thin amber strip shown at the top of the portal when
 * NEXT_PUBLIC_USE_MOCK_DATA=true. Rendered by the AppShell above the Topbar.
 */
export function DemoBanner() {
  if (process.env.NEXT_PUBLIC_USE_MOCK_DATA !== "true") {
    return null;
  }

  return (
    <div
      role="status"
      aria-label="Demo mode active"
      className="bg-amber-500/90 text-amber-950 text-xs font-medium px-4 py-1 text-center w-full sticky top-0 z-50 shrink-0"
    >
      Demo Data — connect backend to see live data
    </div>
  );
}
