import { Construction } from "lucide-react";

interface ComingSoonPageProps {
  title: string;
  description?: string;
  phase?: string;
}

/**
 * Standard placeholder for routes that exist in the sidebar but haven't
 * been built yet. Phase 1B agents will replace each of these with the real page.
 */
export function ComingSoonPage({
  title,
  description,
  phase = "Phase 1B",
}: ComingSoonPageProps) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
          {phase}
        </span>
        <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-ifx-gray-400">{description}</p>
        )}
      </div>

      <div className="flex flex-col items-center justify-center gap-4 rounded-lg bg-white ifx-card-shadow py-16 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-ifx-lavender text-ifx-navy">
          <Construction className="h-6 w-6" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-ifx-gray-900">Coming in {phase}</h2>
          <p className="mt-1 max-w-md text-sm text-ifx-gray-400">
            This page is scaffolded and will be built by a module builder in the
            next phase. The sidebar route resolves correctly and navigation works
            end-to-end.
          </p>
        </div>
      </div>
    </div>
  );
}
