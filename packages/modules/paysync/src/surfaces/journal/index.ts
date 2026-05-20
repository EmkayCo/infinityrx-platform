// packages/modules/paysync/src/surfaces/journal/index.ts
// Journal surface: surface descriptor + public component exports.
// Plan D adds JournalListPage, JournalDetailPage, HashChainVerifyButton
// and BFF route handlers wired to JournalClient from @infinityrx/contract.

import type { SurfaceConfig } from "../../types/surface.js";

export const JournalSurface: SurfaceConfig = {
  id: "journal",
  path: "/admin/paysync/journal",
};

export { JournalListPage, type JournalListPageProps } from "./JournalListPage.js";
export { JournalDetailPage, type JournalDetailPageProps } from "./JournalDetailPage.js";
export { HashChainVerifyButton, type HashChainVerifyButtonProps } from "./HashChainVerifyButton.js";
export {
  handleListJournal,
  handleGetJournalEntry,
  handleVerifyChain,
} from "./bff/journal.js";
