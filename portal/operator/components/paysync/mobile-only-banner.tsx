"use client";

// Wrap complex action surfaces (close wizard, manual entry, template
// editor) so mobile users see a friendly redirect instead of a
// broken layout. Read-only paysync pages remain fully responsive.

import { Smartphone } from "lucide-react";

export function MobileOnlyBanner({ feature }: { feature: string }) {
  return (
    <div className="lg:hidden mx-auto max-w-md rounded-lg border border-amber-500/40 bg-amber-500/5 p-6 text-center">
      <Smartphone className="mx-auto mb-3 h-8 w-8 text-amber-500" />
      <p className="text-sm font-semibold">Best on desktop</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {feature} requires a wider screen for accuracy. Read-only paysync
        views are mobile-friendly; complex actions (cycle close, manual
        entry, template editing) are desktop-only.
      </p>
    </div>
  );
}
