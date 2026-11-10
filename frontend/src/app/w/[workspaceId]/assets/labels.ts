import type { AssetLifecycle, AssetType } from "@/lib/types";

export const ASSET_TYPE_LABEL: Record<AssetType, string> = {
  repository: "Repository",
  service: "Service",
  project: "Project",
  process: "Process",
  vendor: "Vendor / account",
  document_collection: "Documents",
  customer_account: "Customer account",
  infrastructure: "Infrastructure",
  other: "Other",
};

export const LIFECYCLE_LABEL: Record<AssetLifecycle, string> = {
  planned: "Planned",
  active: "Active",
  deprecated: "Deprecated",
  retired: "Retired",
};

/** "contract_renewal" -> "Contract renewal". */
export const fieldLabel = (key: string) =>
  key.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());

export const ASSET_TYPES = Object.keys(ASSET_TYPE_LABEL) as AssetType[];
