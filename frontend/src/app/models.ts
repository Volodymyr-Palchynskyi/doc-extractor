// Mirrors backend/app/schemas. Numbers and dates arrive as JSON numbers and ISO strings.

export interface Party {
  name: string;
  address: string | null;
  tax_id: string | null;
}

export interface LineItem {
  description: string;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface InvoiceExtraction {
  vendor: Party;
  buyer: Party;
  invoice_number: string;
  issue_date: string;
  due_date: string | null;
  currency: string;
  line_items: LineItem[];
  subtotal: number;
  discount_total: number;
  tax_total: number;
  total: number;
}

export type Severity = 'error' | 'warning';

export interface Issue {
  code: string;
  severity: Severity;
  /** Where the problem is, e.g. 'total' or 'line_items[2].line_total'. */
  field: string;
  message: string;
}

export interface Usage {
  model: string;
  input_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  total_tokens: number;
  latency_s: number;
  estimated_cost_usd: number | null;
}

export interface ExtractionResult {
  extraction: InvoiceExtraction;
  issues: Issue[];
  needs_review: boolean;
  usage: Usage | null;
  document_id: string | null;
  pages: number | null;
}

export interface ValidationResult {
  issues: Issue[];
  needs_review: boolean;
}

export interface AppInfo {
  mode: 'gemini' | 'demo';
  max_upload_mb: number;
  max_pages: number;
  document_ttl_s: number;
}

export interface SampleInfo {
  id: string;
  title: string;
  description: string;
  file_name: string;
}
