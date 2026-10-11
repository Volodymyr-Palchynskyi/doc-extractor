import { TestBed } from '@angular/core/testing';
import { ApiClient, ApiError, describeFailure } from './api-client';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

describe('ApiClient', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let api: ApiClient;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    api = TestBed.inject(ApiClient);
  });

  afterEach(() => vi.unstubAllGlobals());

  it('reads app info', async () => {
    fetchMock.mockResolvedValue(json({ mode: 'demo', max_upload_mb: 10, max_pages: 20, document_ttl_s: 900 }));

    expect((await api.info()).mode).toBe('demo');
    expect(fetchMock.mock.calls[0][0]).toMatch(/\/info$/);
  });

  it('uploads the file as multipart form data under the field name "file"', async () => {
    fetchMock.mockResolvedValue(json({ document_id: 'abc' }));
    const file = new Blob(['%PDF-1.7'], { type: 'application/pdf' });

    await api.extract(file, 'invoice.pdf');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get('file')).toBeInstanceOf(File);
    expect(((init.body as FormData).get('file') as File).name).toBe('invoice.pdf');
  });

  it('sends edited values to the validator as JSON', async () => {
    fetchMock.mockResolvedValue(json({ issues: [], needs_review: false }));

    await api.validate({ invoice_number: 'X' } as never);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/validations$/);
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(init.body)).toEqual({ invoice_number: 'X' });
  });

  it('turns an API error into an ApiError carrying the server message', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Only PDF files are supported.' }, 415));

    await expect(api.extract(new Blob(['x']), 'x.png')).rejects.toMatchObject({ status: 415, message: 'Only PDF files are supported.' });
  });

  it('reports an unreachable server in plain words', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await api.info().catch((e) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0 });
    expect(error.message).toMatch(/Cannot reach the server/);
  });

  it('lets a cancellation through untouched so callers can tell it from a failure', async () => {
    fetchMock.mockRejectedValue(new DOMException('aborted', 'AbortError'));

    await expect(api.info()).rejects.toMatchObject({ name: 'AbortError' });
  });

  it('never throws when deleting a document fails', async () => {
    fetchMock.mockRejectedValue(new TypeError('offline'));

    await expect(api.deleteDocument('abc')).resolves.toBeUndefined();
  });

  it('builds page image URLs and encodes the id', () => {
    expect(api.pageUrl('a/b c', 2)).toMatch(/\/documents\/a%2Fb%20c\/pages\/2\.png$/);
  });
});

describe('describeFailure', () => {
  it('uses a plain-text detail from the server', async () => {
    expect(await describeFailure(json({ detail: 'Rate limit reached. Try again in 5 s.' }, 429))).toBe('Rate limit reached. Try again in 5 s.');
  });

  it('does not show a raw validation error list', async () => {
    const message = await describeFailure(json({ detail: [{ loc: ['body', 'total'], msg: 'bad' }] }, 422));

    expect(message).toBe('The request failed (status 422).');
  });

  it('falls back by status when the body is not JSON', async () => {
    expect(await describeFailure(new Response('<html>', { status: 413 }))).toBe('The file is too large.');
    expect(await describeFailure(new Response('', { status: 503 }))).toMatch(/busy or not configured/);
    expect(await describeFailure(new Response('', { status: 502 }))).toBe('The request failed (status 502).');
  });
});
