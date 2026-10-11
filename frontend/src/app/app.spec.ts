import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ApiClient, ApiError } from './api-client';
import { App } from './app';
import { RECHECK_DELAY_MS } from './review-store';
import { ExtractionResult, InvoiceExtraction, Issue, SampleInfo } from './models';

const extraction: InvoiceExtraction = {
  vendor: { name: 'Meridian Works GmbH', address: null, tax_id: null },
  buyer: { name: 'Harbor Consulting KG', address: null, tax_id: null },
  invoice_number: 'RE-2026-5687',
  issue_date: '2026-08-04',
  due_date: '2026-09-18',
  currency: 'EUR',
  line_items: [
    { description: 'Systemintegration', quantity: 2, unit_price: 100, line_total: 200 },
    { description: 'Wartung', quantity: 1, unit_price: 50, line_total: 50 },
  ],
  subtotal: 250,
  discount_total: 0,
  tax_total: 47.5,
  total: 999, // wrong on purpose: 250 + 47.5 = 297.5
};

const totalMismatch: Issue = {
  code: 'total_mismatch', severity: 'error', field: 'total',
  message: 'Subtotal 250.00 - discount 0.00 + tax 47.50 = 297.50, but the total is 999.00.',
};

const sample: SampleInfo = { id: 'german', title: 'German invoice with a wrong total', description: 'The total does not match its lines.', file_name: 'german.pdf' };

const extractionResult: ExtractionResult = {
  extraction, issues: [totalMismatch], needs_review: true,
  usage: { model: 'test-model', input_tokens: 1, output_tokens: 1, thinking_tokens: 0, total_tokens: 2000, latency_s: 9.8, estimated_cost_usd: null },
  document_id: 'doc-1', pages: 2,
};

describe('App', () => {
  let api: Record<string, ReturnType<typeof vi.fn>>;
  let fixture: ComponentFixture<App>;
  const root = () => fixture.nativeElement as HTMLElement;
  const $ = <T extends HTMLElement>(selector: string) => root().querySelector<T>(selector);
  /**
   * Let pending promises and timers run, then render. In zoneless mode whenStable() does not wait for plain
   * promises, so a macrotask turn is needed; with fake timers that turn has to be advanced by hand.
   */
  const settle = async () => {
    for (let round = 0; round < 3; round++) {
      if (vi.isFakeTimers()) await vi.advanceTimersByTimeAsync(0);
      else await new Promise<void>((resolve) => setTimeout(resolve));
      fixture.detectChanges();
    }
  };

  async function start(mode: 'demo' | 'gemini' = 'demo') {
    api['info'].mockResolvedValue({ mode, max_upload_mb: 10, max_pages: 20, document_ttl_s: 900 });
    fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await settle();
  }

  const chooseSample = async () => {
    root().querySelector<HTMLButtonElement>('.sample button')!.click();
    await settle();
    await settle();
  };

  beforeEach(() => {
    api = {
      info: vi.fn(),
      samples: vi.fn().mockResolvedValue([sample]),
      samplePdf: vi.fn().mockResolvedValue(new Blob(['%PDF-1.7'], { type: 'application/pdf' })),
      extract: vi.fn().mockResolvedValue(extractionResult),
      validate: vi.fn().mockResolvedValue({ issues: [], needs_review: false }),
      deleteDocument: vi.fn().mockResolvedValue(undefined),
      pageUrl: vi.fn((id: string, page: number) => `/api/v1/documents/${id}/pages/${page}.png`),
    };
    TestBed.configureTestingModule({ providers: [{ provide: ApiClient, useValue: api }] });
  });

  afterEach(() => vi.useRealTimers());

  it('offers the samples and says plainly that this is demo mode', async () => {
    await start('demo');

    expect(root().textContent).toContain('Demo mode');
    expect(root().querySelectorAll('.sample')).toHaveLength(1);
    expect(root().textContent).toContain('German invoice with a wrong total');
  });

  it('does not show the demo notice for a live model', async () => {
    await start('gemini');

    expect($('.demo')).toBeNull();
    expect(root().textContent).toContain('Live model');
  });

  it('runs a sample through extraction and shows what needs review, with the page next to it', async () => {
    await start();
    await chooseSample();

    expect(api['samplePdf']).toHaveBeenCalledWith('german');
    expect(api['extract']).toHaveBeenCalledTimes(1);
    expect(root().textContent).toContain('Needs review');
    expect(root().textContent).toContain(totalMismatch.message);
    expect($<HTMLInputElement>('#f-total')?.value).toBe('999');
    expect($<HTMLImageElement>('app-page-viewer img')?.getAttribute('src')).toBe('/api/v1/documents/doc-1/pages/1.png');
    expect(root().textContent).toContain('Page 1 of 2');
  });

  it('jumps to the field an issue is about', async () => {
    await start();
    await chooseSample();

    root().querySelector<HTMLButtonElement>('.issue')!.click();

    expect(document.activeElement?.id).toBe('f-total');
  });

  it('re-checks after the user fixes the total and turns the summary green', async () => {
    await start();
    await chooseSample();
    vi.useFakeTimers();

    const input = $<HTMLInputElement>('#f-total')!;
    input.value = '297.5';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    expect(root().textContent).toContain('edited');

    await vi.advanceTimersByTimeAsync(RECHECK_DELAY_MS);
    await settle();

    expect(api['validate']).toHaveBeenCalledTimes(1);
    expect(api['validate'].mock.calls[0][0].total).toBe(297.5);
    expect(root().textContent).toContain('Looks consistent');
    expect(root().textContent).toContain('with your edits');
  });

  it('flags a value that is not a number and does not bother the server with it', async () => {
    await start();
    await chooseSample();
    vi.useFakeTimers();

    const input = $<HTMLInputElement>('#f-total')!;
    input.value = '12abc';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(RECHECK_DELAY_MS);
    await settle();

    expect(api['validate']).not.toHaveBeenCalled();
    expect(root().textContent).toContain('"12abc" is not a number.');
    expect(root().querySelector<HTMLButtonElement>('.actions .btn.primary')!.disabled).toBe(true);
  });

  it('frees the server copy and returns to the start when asked to check another document', async () => {
    await start();
    await chooseSample();

    [...root().querySelectorAll<HTMLButtonElement>('.actions .btn')].find((b) => b.textContent?.includes('another'))!.click();
    await settle();

    expect(api['deleteDocument']).toHaveBeenCalledWith('doc-1');
    expect($('app-upload-panel')).not.toBeNull();
    expect($('app-review-panel')).toBeNull();
  });

  it('shows the server message and stays on the start screen when extraction fails', async () => {
    api['extract'].mockRejectedValue(new ApiError(422, 'Demo mode only accepts the bundled sample documents.'));
    await start();
    await chooseSample();

    expect(root().textContent).toContain('Demo mode only accepts the bundled sample documents.');
    expect($('app-upload-panel')).not.toBeNull();
  });

  it('still lets the user upload when the sample list cannot be loaded', async () => {
    api['samples'].mockRejectedValue(new ApiError(0, 'Cannot reach the server. Is the API running?'));
    await start();

    expect(root().textContent).toContain('Cannot reach the server');
    expect($('app-upload-panel')).not.toBeNull();
  });
});
