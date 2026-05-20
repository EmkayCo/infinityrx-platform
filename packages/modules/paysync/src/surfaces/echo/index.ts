// packages/modules/paysync/src/surfaces/echo/index.ts
// Echo Spec 400 surface — Wave 41 M6 operator page for listing Spec 400 runs,
// status file ingestions, and manual candor pipeline triggers.
//
// Bundle exclusion: this file exports only a static SurfaceConfig constant (no
// React components, no side-effect imports). Tree-shaking removes it from any
// bundle that does not import EchoSurface. No explicit process.env guard is
// needed. The portal shell only registers surfaces listed in module.config.ts
// routes, so echo is unreachable in builds where module.config.ts omits it.
import type { SurfaceConfig } from "../../types/surface.js";

export const EchoSurface: SurfaceConfig = {
  id: "echo",
  path: "/admin/paysync/echo",
};
