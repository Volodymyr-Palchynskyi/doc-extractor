import { InvoiceExtraction, Issue } from './models';

/**
 * The editable form works on TEXT, exactly what the user typed, and is converted to an InvoiceExtraction only
 * when it is valid. Holding numbers directly would lose the difference between "empty", "12," and "12", and
 * would make it impossible to tell the user which field is not a number.
 *
 * Control keys equal the backend's issue paths ('total', 'line_items[2].line_total'), so an issue from the
 * validator finds its input without any mapping table.
 */

export const SCALAR_KEYS = [
  'vendor.name', 'vendor.address', 'vendor.tax_id',
  'buyer.name', 'buyer.address', 'buyer.tax_id',
  'invoice_number', 'issue_date', 'due_date', 'currency',
  'subtotal', 'discount_total', 'tax_total', 'total',
] as const;
export type ScalarKey = (typeof SCALAR_KEYS)[number];

const NUMBER_KEYS: readonly ScalarKey[] = ['subtotal', 'discount_total', 'tax_total', 'total'];
const OPTIONAL_KEYS: readonly ScalarKey[] = ['vendor.address', 'vendor.tax_id', 'buyer.address', 'buyer.tax_id', 'due_date'];

export const LINE_PROPS = ['description', 'quantity', 'unit_price', 'line_total'] as const;
export type LineProp = (typeof LINE_PROPS)[number];

export interface FormLine {
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
}

export interface FormState {
  fields: Record<ScalarKey, string>;
  lines: FormLine[];
}

export const lineKey = (index: number, prop: LineProp): string => `line_items[${index}].${prop}`;

// ---------------------------------------------------------------- invoice <-> form

const text = (value: string | null | undefined): string => value ?? '';

export function fromInvoice(invoice: InvoiceExtraction): FormState {
  return {
    fields: {
      'vendor.name': invoice.vendor.name,
      'vendor.address': text(invoice.vendor.address),
      'vendor.tax_id': text(invoice.vendor.tax_id),
      'buyer.name': invoice.buyer.name,
      'buyer.address': text(invoice.buyer.address),
      'buyer.tax_id': text(invoice.buyer.tax_id),
      invoice_number: invoice.invoice_number,
      issue_date: invoice.issue_date,
      due_date: text(invoice.due_date),
      currency: invoice.currency,
      subtotal: String(invoice.subtotal),
      discount_total: String(invoice.discount_total),
      tax_total: String(invoice.tax_total),
      total: String(invoice.total),
    },
    lines: invoice.line_items.map((item) => ({
      description: item.description,
      quantity: String(item.quantity),
      unit_price: String(item.unit_price),
      line_total: String(item.line_total),
    })),
  };
}

/** Accepts "1234.56" and "1234,56" (people type both); thousands separators and stray text are rejected. */
export function parseNumber(input: string): number | null {
  const cleaned = input.trim();
  if (!/^[-+]?\d+([.,]\d+)?$/.test(cleaned)) return null;
  return Number(cleaned.replace(',', '.'));
}

/** Strict YYYY-MM-DD that is also a real calendar date (rejects 2026-02-30). */
export function isIsoDate(input: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input)) return false;
  const [y, m, d] = input.split('-').map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === m - 1 && date.getUTCDate() === d;
}

const clientError = (field: string, code: string, message: string): Issue => ({ code, severity: 'error', field, message });

export interface Conversion {
  /** Null when at least one field cannot be read, see `errors`. */
  invoice: InvoiceExtraction | null;
  errors: Issue[];
}

export function toInvoice(form: FormState): Conversion {
  const errors: Issue[] = [];
  const f = form.fields;

  const number = (key: string, value: string): number => {
    const parsed = parseNumber(value);
    if (parsed === null) {
      errors.push(clientError(key, 'not_a_number', value.trim() === '' ? 'Required: enter a number.' : `"${value}" is not a number.`));
      return 0;
    }
    return parsed;
  };
  const optional = (key: ScalarKey): string | null => (f[key].trim() === '' ? null : f[key].trim());

  const issue_date = f.issue_date.trim();
  if (!isIsoDate(issue_date)) errors.push(clientError('issue_date', 'invalid_date', 'Enter a valid date (YYYY-MM-DD).'));
  const due = optional('due_date');
  if (due !== null && !isIsoDate(due)) errors.push(clientError('due_date', 'invalid_date', 'Enter a valid date (YYYY-MM-DD) or leave empty.'));

  const line_items = form.lines.map((line, i) => ({
    description: line.description,
    quantity: number(lineKey(i, 'quantity'), line.quantity),
    unit_price: number(lineKey(i, 'unit_price'), line.unit_price),
    line_total: number(lineKey(i, 'line_total'), line.line_total),
  }));

  const invoice: InvoiceExtraction = {
    vendor: { name: f['vendor.name'], address: optional('vendor.address'), tax_id: optional('vendor.tax_id') },
    buyer: { name: f['buyer.name'], address: optional('buyer.address'), tax_id: optional('buyer.tax_id') },
    invoice_number: f.invoice_number.trim(),
    issue_date,
    due_date: due,
    currency: f.currency.trim().toUpperCase(),
    line_items,
    subtotal: number('subtotal', f.subtotal),
    discount_total: number('discount_total', f.discount_total),
    tax_total: number('tax_total', f.tax_total),
    total: number('total', f.total),
  };
  return { invoice: errors.length ? null : invoice, errors };
}

// ---------------------------------------------------------------- immutable edits

export function setScalar(form: FormState, key: ScalarKey, value: string): FormState {
  return { ...form, fields: { ...form.fields, [key]: value } };
}

export function setLine(form: FormState, index: number, prop: LineProp, value: string): FormState {
  return { ...form, lines: form.lines.map((line, i) => (i === index ? { ...line, [prop]: value } : line)) };
}

export function addLine(form: FormState): FormState {
  return { ...form, lines: [...form.lines, { description: '', quantity: '1', unit_price: '0', line_total: '0' }] };
}

export function removeLine(form: FormState, index: number): FormState {
  return { ...form, lines: form.lines.filter((_, i) => i !== index) };
}

// ---------------------------------------------------------------- what changed since extraction

/** Keys of every control whose text differs from the extraction. Added lines count as fully changed. */
export function changedKeys(original: FormState, current: FormState): Set<string> {
  const changed = new Set<string>();
  for (const key of SCALAR_KEYS) {
    if (original.fields[key] !== current.fields[key]) changed.add(key);
  }
  current.lines.forEach((line, i) => {
    const before = original.lines[i];
    for (const prop of LINE_PROPS) {
      if (before === undefined || before[prop] !== line[prop]) changed.add(lineKey(i, prop));
    }
  });
  if (original.lines.length !== current.lines.length) changed.add('line_items');
  return changed;
}

// ---------------------------------------------------------------- issues

export function issuesByField(issues: Issue[]): Map<string, Issue[]> {
  const grouped = new Map<string, Issue[]>();
  for (const issue of issues) grouped.set(issue.field, [...(grouped.get(issue.field) ?? []), issue]);
  return grouped;
}

/** Errors first, then warnings, otherwise keep the validator's order. */
export function sortIssues(issues: Issue[]): Issue[] {
  const rank = (issue: Issue) => (issue.severity === 'error' ? 0 : 1);
  return [...issues].sort((a, b) => rank(a) - rank(b));
}

// ---------------------------------------------------------------- export

/**
 * Quote a CSV cell. A cell that starts with = + - @ is also prefixed with an apostrophe: spreadsheets would
 * otherwise run it as a formula, and invoice text comes from outside.
 */
export function csvCell(value: string): string {
  const safe = /^[=+\-@\t\r]/.test(value) ? `'${value}` : value;
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function lineItemsToCsv(invoice: InvoiceExtraction): string {
  const rows = invoice.line_items.map((item) =>
    [csvCell(item.description), item.quantity, item.unit_price, item.line_total].join(','),
  );
  return ['description,quantity,unit_price,line_total', ...rows].join('\n') + '\n';
}

export function isNumberKey(key: string): boolean {
  return (NUMBER_KEYS as readonly string[]).includes(key);
}

export function isOptionalKey(key: string): boolean {
  return (OPTIONAL_KEYS as readonly string[]).includes(key);
}
