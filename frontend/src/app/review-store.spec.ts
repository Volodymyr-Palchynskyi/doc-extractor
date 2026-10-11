import { TestBed } from '@angular/core/testing';
import { ApiClient } from './api-client';
import { ExtractionResult, InvoiceExtraction, Issue, ValidationResult } from './models';
import { RECHECK_DELAY_MS, ReviewStore } from './review-store';

const extraction: InvoiceExtraction = {
  vendor: { name: 'Acme GmbH', address: null, tax_id: null },
  buyer: { name: 'Beta Ltd', address: null, tax_id: null },
  invoice_number: 'INV-001',
  issue_date: '2026-03-01',
  due_date: null,
  currency: 'EUR',
  line_items: [{ description: 'Widget', quantity: 2, unit_price: 50, line_total: 100 }],
  subtotal: 100,
  discount_total: 0,
  tax_total: 19,
  total: 119,
};

const totalMismatch: Issue = { code: 'total_mismatch', severity: 'error', field: 'total', message: 'wrong total' };

const result = (issues: Issue[] = []): ExtractionResult => ({
  extraction, issues, needs_review: issues.length > 0, usage: null, document_id: 'doc1', pages: 1,
});

/** A promise the test resolves by hand, to control the order in which responses arrive. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

describe('ReviewStore', () => {
  let validate: ReturnType<typeof vi.fn>;
  let store: ReviewStore;

  beforeEach(() => {
    vi.useFakeTimers();
    validate = vi.fn().mockResolvedValue({ issues: [], needs_review: false } satisfies ValidationResult);
    TestBed.configureTestingModule({ providers: [ReviewStore, { provide: ApiClient, useValue: { validate } }] });
    store = TestBed.inject(ReviewStore);
  });

  afterEach(() => vi.useRealTimers());

  const wait = () => vi.advanceTimersByTimeAsync(RECHECK_DELAY_MS);

  it('starts from the issues the extraction came with', () => {
    store.load(result([totalMismatch]));

    expect(store.issues()).toEqual([totalMismatch]);
    expect(store.errorCount()).toBe(1);
    expect(store.edited()).toBe(false);
    expect(validate).not.toHaveBeenCalled();
  });

  it('re-checks once after a burst of edits, not after every keystroke', async () => {
    store.load(result([totalMismatch]));

    store.setScalar('total', '1');
    store.setScalar('total', '11');
    store.setScalar('total', '119');
    expect(validate).not.toHaveBeenCalled();
    await wait();

    expect(validate).toHaveBeenCalledTimes(1);
    expect(validate.mock.calls[0][0].total).toBe(119);
    expect(store.issues()).toEqual([]);
  });

  it('does not call the server while a field is unreadable, and says which one', async () => {
    store.load(result());

    store.setScalar('total', '12abc');
    await wait();

    expect(validate).not.toHaveBeenCalled();
    expect(store.issues().map((i) => i.field)).toEqual(['total']);
    expect(store.correctedInvoice()).toBeNull();

    store.setScalar('total', '119');
    await wait();
    expect(validate).toHaveBeenCalledTimes(1);
    expect(store.issues()).toEqual([]);
    expect(store.correctedInvoice()?.total).toBe(119);
  });

  it('ignores a slow answer that arrives after a newer one', async () => {
    store.load(result());
    const slow = deferred<ValidationResult>();
    const fast = deferred<ValidationResult>();
    validate.mockReturnValueOnce(slow.promise).mockReturnValueOnce(fast.promise);

    store.setScalar('total', '1');
    await wait(); // first check starts and hangs
    store.setScalar('total', '2');
    await wait(); // second check supersedes it
    fast.resolve({ issues: [], needs_review: false });
    await vi.advanceTimersByTimeAsync(0);
    slow.resolve({ issues: [totalMismatch], needs_review: true }); // stale, must be dropped
    await vi.advanceTimersByTimeAsync(0);

    expect(store.issues()).toEqual([]);
    expect(store.checking()).toBe(false);
  });

  it('cancels the request that was superseded', async () => {
    store.load(result());
    validate.mockReturnValue(new Promise(() => undefined));

    store.setScalar('total', '1');
    await wait();
    const firstSignal: AbortSignal = validate.mock.calls[0][1];
    store.setScalar('total', '2');
    await wait();

    expect(firstSignal.aborted).toBe(true);
  });

  it('keeps the previous issues and reports a failed re-check', async () => {
    store.load(result([totalMismatch]));
    validate.mockRejectedValue(new Error('Too many requests.'));

    store.setScalar('tax_total', '20');
    await wait();

    expect(store.issues()).toEqual([totalMismatch]);
    expect(store.checkError()).toBe('Too many requests.');
    expect(store.checking()).toBe(false);
  });

  it('tracks which controls were edited, and forgets an undone edit', () => {
    store.load(result());

    store.setScalar('total', '5');
    store.setLine(0, 'quantity', '3');
    expect([...store.changed()].sort()).toEqual(['line_items[0].quantity', 'total']);
    expect(store.edited()).toBe(true);

    store.setScalar('total', '119');
    expect([...store.changed()]).toEqual(['line_items[0].quantity']);
  });

  it('adds and removes lines', () => {
    store.load(result());

    store.addLine();
    expect(store.form()?.lines).toHaveLength(2);
    expect(store.changed().has('line_items')).toBe(true);

    store.removeLine(1);
    store.removeLine(0);
    expect(store.form()?.lines).toHaveLength(0);
  });

  it('puts the extraction back with resetEdits, issues included', async () => {
    store.load(result([totalMismatch]));
    store.setScalar('total', '119');
    await wait();
    expect(store.issues()).toEqual([]);

    store.resetEdits();

    expect(store.edited()).toBe(false);
    expect(store.form()?.fields.total).toBe('119');
    expect(store.issues()).toEqual([totalMismatch]);
  });

  it('forgets everything on reset and never fires a pending check afterwards', async () => {
    store.load(result());
    store.setScalar('total', '1');
    store.reset();
    await wait();

    expect(store.result()).toBeNull();
    expect(store.form()).toBeNull();
    expect(validate).not.toHaveBeenCalled();
  });

  it('sorts errors before warnings', () => {
    const warning: Issue = { code: 'unknown_currency', severity: 'warning', field: 'currency', message: 'odd' };
    store.load(result([warning, totalMismatch]));

    expect(store.issues().map((i) => i.severity)).toEqual(['error', 'warning']);
    expect(store.warningCount()).toBe(1);
  });
});
