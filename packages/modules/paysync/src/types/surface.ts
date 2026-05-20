// packages/modules/paysync/src/types/surface.ts
// Module-local type for surface descriptors. Not shared via @infinityrx/shell —
// surfaces are an internal composition concern of paysync.

export interface SurfaceConfig {
  readonly id: string;
  readonly path: string;
}
