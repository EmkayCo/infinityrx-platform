// packages/modules/paysync/src/surfaces/files/index.ts
// Files surface: surface descriptor + public component exports.
// Plan D adds FilesListPage, FileDetailPage, FileGenerateForm and BFF route handlers.

import type { SurfaceConfig } from "../../types/surface.js";

export const FilesSurface: SurfaceConfig = {
  id: "files",
  path: "/admin/paysync/files",
};

export { FilesListPage, type FilesListPageProps } from "./FilesListPage.js";
export { FileDetailPage, type FileDetailPageProps } from "./FileDetailPage.js";
export { FileGenerateForm, type FileGenerateFormProps } from "./FileGenerateForm.js";
export {
  handleListFiles,
  handleGetFile,
  handleGenerateFile,
  handleDownloadFile,
} from "./bff/files.js";
