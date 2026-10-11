import {
  addLine, changedKeys, csvCell, fromInvoice, isIsoDate, issuesByField, lineItemsToCsv, lineKey, parseNumber,
  removeLine, setLine, setScalar, sortIssues, toInvoice,
} from './invoice-form';
import { InvoiceExtraction, Issue } from './models';

function invoice(overrides: Partial<InvoiceExtraction> = {}): InvoiceExtraction {
  return {
    vendor: { name: 'Acme GmbH', address: 'Hauptstrasse 1, Berlin', tax_id: 'DE123456789' },
    buyer: { name: 'Beta Ltd', address: null, tax_id: null },
    invoice_number: 'INV-001',
    issue_date: '2026-03-01',
    due_date: '2026-03-31',
    currency: 'EUR',
    line_items: [
      { description: 'Widget', quantity: 2, unit_price: 50, line_total: 100 },
      { description: 'Gadget', quantity: 1.5, unit_price: 19.99, line_total: 29.99 },
    ],
    subtotal: 129.99,
    discount_total: 0,
    tax_total: 24.7,
    total: 154.69,
    ...overrides,
  };
}

const issue = (field: string, severity: Issue['severity'] = 'error'): Issue => ({ code: 'x', severity, field, message: field });

describe('parseNumber', () => {
  it.each([['12', 12], ['12.5', 12.5], ['12,5', 12.5], [' 7 ', 7], ['-3', -3], ['0', 0], ['+4.25', 4.25]])('reads %j', (text, expected) => {
    expect(parseNumber(text)).toBe(expected);
  });

  it.each(['', ' ', 'abc', '12abc', '1 234', '1,234.56', '1.234,56', '12.', '.5', '1e3', 'NaN'])('rejects %j', (text) => {
    expect(parseNumber(text)).toBeNull();
  });
});

describe('isIsoDate', () => {
  it('accepts real calendar dates only', () => {
    expect(isIsoDate('2026-02-28')).toBe(true);
    expect(isIsoDate('2028-02-29')).toBe(true);
    expect(isIsoDate('2026-02-29')).toBe(false);
    expect(isIsoDate('2026-02-30')).toBe(false);
    expect(isIsoDate('2026-13-01')).toBe(false);
    expect(isIsoDate('01/03/2026')).toBe(false);
    expect(isIsoDate('')).toBe(false);
  });
});

describe('fromInvoice / toInvoice', () => {
  it('round-trips an invoice unchanged', () => {
    const original = invoice();
    const { invoice: back, errors } = toInvoice(fromInvoice(original));

    expect(errors).toEqual([]);
    expect(back).toEqual(original);
  });

  it('turns blank optional fields into null and trims text', () => {
    let form = fromInvoice(invoice());
    form = setScalar(form, 'due_date', '');
    form = setScalar(form, 'vendor.tax_id', '   ');
    form = setScalar(form, 'invoice_number', '  INV-9 ');
    const { invoice: back } = toInvoice(form);

    expect(back?.due_date).toBeNull();
    expect(back?.vendor.tax_id).toBeNull();
    expect(back?.invoice_number).toBe('INV-9');
  });

  it('normalises the currency code', () => {
    expect(toInvoice(setScalar(fromInvoice(invoice()), 'currency', ' eur ')).invoice?.currency).toBe('EUR');
  });

  it('reports every unreadable number with the key of its control', () => {
    let form = fromInvoice(invoice());
    form = setScalar(form, 'total', '12abc');
    form = setScalar(form, 'tax_total', '');
    form = setLine(form, 1, 'quantity', 'two');
    const { invoice: back, errors } = toInvoice(form);

    expect(back).toBeNull();
    expect(errors.map((e) => e.field).sort()).toEqual(['line_items[1].quantity', 'tax_total', 'total'].sort());
    expect(errors.find((e) => e.field === 'tax_total')?.message).toMatch(/Required/);
    expect(errors.find((e) => e.field === 'total')?.message).toContain('12abc');
  });

  it('reports a bad issue date, and a bad due date only when one was typed', () => {
    let form = setScalar(fromInvoice(invoice()), 'issue_date', '2026-02-30');
    expect(toInvoice(form).errors.map((e) => e.field)).toEqual(['issue_date']);

    form = setScalar(setScalar(form, 'issue_date', '2026-03-01'), 'due_date', 'soon');
    expect(toInvoice(form).errors.map((e) => e.field)).toEqual(['due_date']);

    form = setScalar(form, 'due_date', '');
    expect(toInvoice(form).errors).toEqual([]);
  });

  it('accepts a comma decimal the way people type it', () => {
    expect(toInvoice(setScalar(fromInvoice(invoice()), 'total', '154,69')).invoice?.total).toBe(154.69);
  });
});

describe('immutable edits', () => {
  it('never mutates the previous state', () => {
    const before = fromInvoice(invoice());
    const snapshot = structuredClone(before);

    setScalar(before, 'total', '1');
    setLine(before, 0, 'description', 'changed');
    addLine(before);
    removeLine(before, 0);

    expect(before).toEqual(snapshot);
  });

  it('adds and removes lines', () => {
    let form = fromInvoice(invoice());
    form = addLine(form);
    expect(form.lines).toHaveLength(3);
    form = removeLine(form, 0);
    expect(form.lines.map((l) => l.description)).toEqual(['Gadget', '']);
  });
});

describe('changedKeys', () => {
  const original = fromInvoice(invoice());

  it('is empty when nothing changed', () => {
    expect(changedKeys(original, structuredClone(original)).size).toBe(0);
  });

  it('lists scalar and line edits by control key', () => {
    let current = setScalar(original, 'total', '999');
    current = setLine(current, 1, 'line_total', '30');

    expect([...changedKeys(original, current)].sort()).toEqual(['line_items[1].line_total', 'total']);
  });

  it('marks an edit that was undone as unchanged', () => {
    const current = setScalar(setScalar(original, 'total', '999'), 'total', original.fields.total);
    expect(changedKeys(original, current).size).toBe(0);
  });

  it('treats an added line as fully changed', () => {
    const keys = changedKeys(original, addLine(original));

    expect(keys.has(lineKey(2, 'description'))).toBe(true);
    expect(keys.has('line_items')).toBe(true);
  });

  it('notes a removed line', () => {
    expect(changedKeys(original, removeLine(original, 1)).has('line_items')).toBe(true);
  });
});

describe('issues', () => {
  it('groups issues by the field they point at', () => {
    const grouped = issuesByField([issue('total'), issue('line_items[0].line_total'), issue('total', 'warning')]);

    expect(grouped.get('total')).toHaveLength(2);
    expect(grouped.get('line_items[0].line_total')).toHaveLength(1);
    expect(grouped.has('subtotal')).toBe(false);
  });

  it('puts errors before warnings and keeps the rest in order', () => {
    const sorted = sortIssues([issue('a', 'warning'), issue('b'), issue('c', 'warning'), issue('d')]);

    expect(sorted.map((i) => i.field)).toEqual(['b', 'd', 'a', 'c']);
  });
});

describe('CSV export', () => {
  it('quotes commas, quotes and line breaks', () => {
    expect(csvCell('plain')).toBe('plain');
    expect(csvCell('a, b')).toBe('"a, b"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell('two\nlines')).toBe('"two\nlines"');
  });

  it('neutralises spreadsheet formulas coming from the document', () => {
    expect(csvCell('=HYPERLINK("http://evil")')).toBe(`"'=HYPERLINK(""http://evil"")"`);
    expect(csvCell('+1')).toBe("'+1");
    expect(csvCell('-2')).toBe("'-2");
    expect(csvCell('@SUM(A1)')).toBe("'@SUM(A1)");
  });

  it('writes a header and one row per line item', () => {
    const csv = lineItemsToCsv(invoice({ line_items: [{ description: 'Cloud, monthly', quantity: 2, unit_price: 10.5, line_total: 21 }] }));

    expect(csv).toBe('description,quantity,unit_price,line_total\n"Cloud, monthly",2,10.5,21\n');
  });
});
