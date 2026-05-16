// packages/modules/prescriber-directory/src/index.ts
// Public surface of @infinityrx/module-prescriber-directory.
// Exports the factory and re-exports the client interface for consumers.
export { createPrescriberDirectoryClient } from "./factory.js";
export type { PrescriberDirectoryClient } from "@infinityrx/contract";
