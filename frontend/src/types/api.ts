// API TypeScript interfaces mirroring backend Pydantic schemas exactly.

// ─── Generic API envelope ────────────────────────────────────────────────────

export interface PaginationMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface ApiResponse<T> {
  success: boolean
  data: T
  meta: PaginationMeta | null
  message: string
}

export interface ApiError {
  success: false
  code: string
  message: string
  details: Record<string, unknown>
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  permissions: string[]
}

export interface UserOut {
  public_id: string
  username: string
  email: string
  full_name: string
  is_active: boolean
  role_name: string
  permissions: string[]
}

// ─── Master ───────────────────────────────────────────────────────────────────

export interface WarehouseOut {
  public_id: string
  name: string
  type: 'ODS' | 'RMPM'
  description: string
  created_at: string
  updated_at: string | null
}

export interface MaterialCategoryOut {
  public_id: string
  name: string
}

export interface MaterialTypeOut {
  public_id: string
  name: string  // 'RM' | 'PM'
}

export interface MaterialGroupOut {
  public_id: string
  name: string
}

export interface MaterialOut {
  public_id: string
  code: string
  name: string
  uom: string
  category: MaterialCategoryOut | null
  material_type: MaterialTypeOut | null
  group: MaterialGroupOut | null
  created_at: string
  updated_at: string | null
}

export interface SKUOut {
  public_id: string
  code: string
  name: string
  description: string
  created_at: string
  updated_at: string | null
}

/** Lightweight projection used for dropdowns — mirrors backend SKUOptionOut. */
export interface SKUOption {
  public_id: string
  code: string
  name: string
}

export interface BOMItemOut {
  public_id: string
  material: MaterialOut
  quantity_per_unit: string  // decimal as string
  material_type: string  // 'RM' | 'PM'
}

export interface BOMVersionOut {
  public_id: string
  version_number: number
  notes: string
  is_active: boolean
  sku: SKUOut
  rm_items: BOMItemOut[]
  pm_items: BOMItemOut[]
  created_at: string
}

export interface BOMUploadRowResult {
  row_number: number
  sku_code: string
  material_code: string
  quantity_per_unit: string
  status: 'valid' | 'error' | 'warning'
  message: string
}

export interface BOMUploadPreview {
  total_rows: number
  valid_rows: number
  error_rows: number
  rows: BOMUploadRowResult[]
  errors: string[]
  warnings: string[]
  skus_affected: string[]
  unknown_materials: string[]
  session_id?: string
  session_status?: string
}

// ─── Material Master Upload ───────────────────────────────────────────────────

export interface MaterialUploadRowResult {
  row_number: number
  material_code: string
  material_name: string
  uom: string
  category: string
  material_type: string
  group: string
  status: 'valid' | 'error' | 'duplicate' | 'skipped'
  message: string
}

export interface MaterialUploadPreview {
  total_rows: number
  valid_rows: number
  error_rows: number
  skipped_rows_count: number
  new_materials: string[]
  updated_materials: string[]
  duplicate_material_codes: string[]
  invalid_rows: string[]
  skipped_rows: string[]
  rows: MaterialUploadRowResult[]
  errors: string[]
  warnings: string[]
}

// ─── Inventory ────────────────────────────────────────────────────────────────

export interface InventoryUploadStats {
  snapshot_date: string | null
  upload_time: string | null
  uploaded_by: string | null
  warehouse_name: string | null
  version: number | null
  total_materials: number
  matched_count: number
  variance_count: number
}

export interface InventoryBalance {
  material_public_id: string
  material_code: string
  material_name: string
  uom: string
  warehouse_public_id: string
  warehouse_name: string
  available_balance: string
  reserved_balance: string
}

export interface InventoryTransactionOut {
  id: number
  transaction_type: string
  quantity: string
  reference_type: string | null
  reference_id: number | null
  notes: string
  created_at: string
  created_by: number
}

export interface OpeningBalanceRow {
  row: number
  material_code: string
  warehouse: string
  uom: string
  quantity: string
  date: string
  status: 'valid' | 'error' | 'warning'
  messages: string[]
}

export interface OpeningBalanceUploadPreview {
  total_rows: number
  valid_rows: number
  error_rows: number
  warning_rows: number
  
  total_materials: number
  total_quantity: string
  duplicates: number
  unknown_materials: number
  negative_quantities: number
  
  rows: OpeningBalanceRow[]
  warnings: string[]
  errors: string[]
}

// ─── Material Requests ────────────────────────────────────────────────────────

export type RequestStatus =
  | 'SUBMITTED'
  | 'APPROVED'
  | 'PARTIALLY_APPROVED'
  | 'DISPATCHED'
  | 'RECEIVED'
  | 'CLOSED'
  | 'REJECTED'

export interface MaterialRequestItemOut {
  public_id: string
  material_id: number
  material_public_id: string
  material_name: string
  material_code: string
  material_type: string  // 'RM' | 'PM'
  gross_required_qty: string
  remaining_from_previous_day: string
  requested_qty: string
  approved_qty: string | null
  dispatched_qty: string | null
  received_qty: string | null
}

export interface MaterialRequestSKUOut {
  public_id: string
  sku_id: number
  planned_production_qty: string
  items: MaterialRequestItemOut[]
}

export interface MaterialRequestOut {
  public_id: string
  request_date: string
  status: RequestStatus
  notes: string
  ods_warehouse_id: number
  rmpm_warehouse_id: number | null
  skus: MaterialRequestSKUOut[]
  created_at: string
  updated_at: string | null
}

export interface MaterialRequestListItem {
  public_id: string
  request_date: string
  status: RequestStatus
  notes: string
  created_at: string
}

// ─── Request create payload ───────────────────────────────────────────────────

export interface RequestSKUInput {
  sku_public_id: string
  planned_production_qty: string
}

export interface CreateRequestPayload {
  request_date: string
  ods_warehouse_public_id: string
  notes: string
  skus: RequestSKUInput[]
}

export interface RequestPreviewPayload extends CreateRequestPayload {}

export interface RequestPreviewItemOut {
  material_public_id: string
  material_name: string
  material_code: string
  material_type: string
  gross_required_qty: string
  remaining_from_previous_day: string
  requested_qty: string
}

export interface RequestPreviewSKUOut {
  sku_public_id: string
  sku_name: string
  sku_code: string
  planned_production_qty: string
  items: RequestPreviewItemOut[]
}

export interface RequestPreviewOut {
  skus: RequestPreviewSKUOut[]
}

export interface ApprovalItemInput {
  material_request_item_public_id: string
  approved_qty: string
}

export interface ApproveRequestPayload {
  rmpm_warehouse_public_id: string
  items: ApprovalItemInput[]
}
