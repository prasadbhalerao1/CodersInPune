import type { AssetType } from "@/lib/types";

export const ASSET_TYPE_LABEL: Record<AssetType, string> = {
  repository: "Repository",
  service: "Service",
  project: "Project",
  process: "Process",
  vendor: "Vendor / account",
  document_collection: "Documents",
  other: "Other",
};

export const ASSET_TYPES = Object.keys(ASSET_TYPE_LABEL) as AssetType[];
