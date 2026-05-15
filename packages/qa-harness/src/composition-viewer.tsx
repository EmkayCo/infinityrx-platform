export interface CompositionManifest {
  /** The list of module names included in this build. */
  modules: string[];
}

export interface CompositionViewerProps {
  manifest: CompositionManifest;
  /** Optional human-readable instance label (e.g. "operator-dev", "reclaimrx-standalone"). */
  instanceLabel?: string;
  className?: string;
}

/**
 * Renders the deployment composition for QA verification:
 * "This build contains: reclaimrx, paysync" — proves the deployment manifest
 * produced the expected artifact. Takes a `manifest` prop.
 *
 * Plan C-shell is responsible for fetching the runtime manifest from
 * `packages/shell/src/_generated/manifest.json` and passing it here.
 * Plan C's component is prop-driven to stay framework-agnostic.
 *
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function CompositionViewer({ manifest, instanceLabel, className }: CompositionViewerProps) {
  return (
    <div className={["irx-qa-composition", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-composition__heading">Build Composition</h2>
      {instanceLabel != null && (
        <p className="irx-qa-composition__instance">{instanceLabel}</p>
      )}
      {manifest.modules.length === 0 ? (
        <p className="irx-qa-composition__empty">No modules in this build.</p>
      ) : (
        <>
          <p className="irx-qa-composition__count">{manifest.modules.length} module(s) included</p>
          <ul className="irx-qa-composition__list">
            {manifest.modules.map((mod) => (
              <li key={mod} className="irx-qa-composition__module">{mod}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
