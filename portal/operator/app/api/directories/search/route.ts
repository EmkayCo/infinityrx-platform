// portal/operator/app/api/directories/search/route.ts
// GET /api/directories/search?q=...&limit=20
// Mounts the federated search BFF handler from @infinityrx/module-directories.
// Auth is enforced inside the handler (verifyTokenRaw + AccessClaimsSchema).
export { GET } from "@infinityrx/module-directories/bff";
