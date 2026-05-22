// packages/modules/paysync/src/surfaces/uploads/index.ts
// Uploads surface: surface descriptor + public component exports.
// Plan B adds the 4 real components (UploadsListPage, UploadDropzone,
// UploadDetailPage, UploadClaimViewer) and BFF route handlers.

import type { SurfaceConfig } from "../../types/surface.js";

export const UploadsSurface: SurfaceConfig = {
  id: "uploads",
  path: "/admin/paysync/uploads",
};

export { UploadsListPage, type UploadsListPageProps, type DedupBanner } from "./UploadsListPage.js";
export { UploadDropzone, type UploadDropzoneProps } from "./UploadDropzone.js";
export { ColumnMappingStep, REQUIRED_FIELDS, type ColumnMappingStepProps } from "./ColumnMappingStep.js";
export { UploadDetailPage, type UploadDetailPageProps, type RowError } from "./UploadDetailPage.js";
export { UploadClaimViewer, type UploadClaimViewerProps } from "./UploadClaimViewer.js";
export {
  handleListUploads,
  handleGetUpload,
  handleGetUploadClaims,
  handleCreateUpload,
} from "./bff/uploads.js";
