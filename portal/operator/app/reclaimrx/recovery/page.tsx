import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { RecoveryRecord } from "@shared/types/reclaimrx";
import { RecoveryInteractive } from "@/components/reclaimrx/recovery-interactive";

// Server Component: fetches recovery data at request time so the initial
// HTML contains real rows instead of a loading skeleton. The interactive
// bits (router navigation, export menu) live in the client leaf.
export default async function RecoveryPage() {
  const records = await apiGet<RecoveryRecord[]>(
    buildUrl(`${API_URLS.reclaimrx}/api/v1/recovery`)
  );

  return (
    <ErrorBoundary>
      <RecoveryInteractive records={records} />
    </ErrorBoundary>
  );
}
