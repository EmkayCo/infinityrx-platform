/**
 * A single nav entry emitted by a module's module.config.ts
 * and consumed by <ModuleNav> to build the sidebar.
 */
export interface NavEntry {
  /** Matches the module id in the deployment manifest. */
  readonly moduleId: string;
  /** Display label. */
  readonly label: string;
  /** Absolute path, e.g. "/reclaimrx". */
  readonly href: string;
  /** Icon identifier for the design system. e.g. "shield-check". */
  readonly iconSlug: string;
  /**
   * Roles that may see this nav entry.
   * Empty array = any authenticated user may see it.
   */
  readonly requiredRoles: readonly string[];
}

/**
 * Minimal shape of the instance manifest consumed by <ModuleNav>.
 * The full schema is in SD-4 §3; we read only what we need here.
 */
export interface InstanceManifestShape {
  readonly instance_name: string;
  readonly modules: readonly string[];
  readonly audience: string;
  /**
   * Metadata written by Plan D's generate-composition.ts codegen.
   * Present in the placeholder (sentinel values) and in real generated artifacts.
   * Plan D's staleness check distinguishes placeholder from real via input_hash
   * all-zeros sentinel.
   */
  readonly _generated?: {
    readonly input_hash: string;
    readonly inputs: readonly string[];
    readonly generated_at: string;
    readonly generator: string;
  };
}
