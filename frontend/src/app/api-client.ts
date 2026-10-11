import { Injectable, isDevMode } from '@angular/core';
import { AppInfo, ExtractionResult, InvoiceExtraction, SampleInfo, ValidationResult } from './models';

/** `ng serve` talks to the API directly (CORS allows localhost:4200); a built app uses the same origin behind nginx. */
const apiBase = () => (isDevMode() ? 'http://localhost:8000/api/v1' : '/api/v1');

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** A readable sentence for the user: the server's own `detail` when it is plain text, otherwise something sensible. */
export async function describeFailure(response: Response): Promise<string> {
  try {
    const body = await response.json();
    // FastAPI sends a string for errors we raise and a list of field errors for malformed requests.
    if (typeof body?.detail === 'string') return body.detail;
  } catch {
    // not JSON, fall through
  }
  if (response.status === 413) return 'The file is too large.';
  if (response.status === 429) return 'Too many requests. Please wait a moment and try again.';
  if (response.status === 503) return 'The service is busy or not configured. Please try again shortly.';
  return `The request failed (status ${response.status}).`;
}

@Injectable({ providedIn: 'root' })
export class ApiClient {
  info(): Promise<AppInfo> {
    return this.json<AppInfo>('/info');
  }

  samples(): Promise<SampleInfo[]> {
    return this.json<SampleInfo[]>('/samples');
  }

  async samplePdf(id: string): Promise<Blob> {
    return (await this.request(`/samples/${encodeURIComponent(id)}/pdf`)).blob();
  }

  extract(file: Blob, fileName: string, signal?: AbortSignal): Promise<ExtractionResult> {
    const body = new FormData();
    body.append('file', file, fileName);
    return this.json<ExtractionResult>('/extractions', { method: 'POST', body, signal });
  }

  validate(invoice: InvoiceExtraction, signal?: AbortSignal): Promise<ValidationResult> {
    return this.json<ValidationResult>('/validations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(invoice),
      signal,
    });
  }

  /** Best effort: the document also expires on its own, so a failure here is not worth showing. */
  async deleteDocument(id: string): Promise<void> {
    try {
      await this.request(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' });
    } catch {
      // ignore
    }
  }

  pageUrl(documentId: string, page: number): string {
    return `${apiBase()}/documents/${encodeURIComponent(documentId)}/pages/${page}.png`;
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    return (await this.request(path, init)).json() as Promise<T>;
  }

  private async request(path: string, init?: RequestInit): Promise<Response> {
    let response: Response;
    try {
      response = await fetch(`${apiBase()}${path}`, init);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') throw error; // the caller cancelled
      throw new ApiError(0, 'Cannot reach the server. Is the API running?');
    }
    if (!response.ok) throw new ApiError(response.status, await describeFailure(response));
    return response;
  }
}
