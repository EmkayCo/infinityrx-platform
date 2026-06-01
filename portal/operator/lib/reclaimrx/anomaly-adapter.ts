/**
 * Operator-layer re-export of the reclaimrx-v2 adapter utilities.
 * Import from here within the operator portal to avoid deep shared-type paths.
 */
export {
  FINDING_CODE_TO_CATEGORY,
  CATEGORY_TO_FINDING_CODES,
  ANOMALY_STATUS_TO_LEAKAGE,
  LEAKAGE_STATUS_TO_ANOMALY,
  anomalyToLeakageFlag,
  buildAnomalyQueryParams,
} from "@shared/types/reclaimrx-v2";

export type {
  AnomalyRead,
  AnomalyListResponse,
  AnomalyFilterValues,
  DetectionRunRead,
  DetectionRunDetail,
} from "@shared/types/reclaimrx-v2";
