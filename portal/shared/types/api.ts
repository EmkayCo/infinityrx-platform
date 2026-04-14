export interface ApiError {
  error: {
    code: string;
    message: string;
    field?: string;
    correlation_id: string;
  };
}

export interface Pagination {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export type SortOrder = "asc" | "desc";

export interface SortParam {
  field: string;
  order: SortOrder;
}

export interface FilterParams {
  [key: string]: string | string[] | number | boolean | null | undefined;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface ApiResponse<T> {
  data: T;
  meta?: Record<string, unknown>;
}
