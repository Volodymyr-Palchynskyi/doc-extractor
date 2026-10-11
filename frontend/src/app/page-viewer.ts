import { ChangeDetectionStrategy, Component, computed, inject, input, linkedSignal, signal } from '@angular/core';
import { ApiClient } from './api-client';

/** Shows the uploaded document page by page, next to the fields, so a human can check values against the source. */
@Component({
  selector: 'app-page-viewer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bar">
      <button type="button" class="btn small" (click)="go(-1)" [disabled]="page() <= 1" aria-label="Previous page">Previous</button>
      <span class="count" aria-live="polite">Page {{ page() }} of {{ pages() }}</span>
      <button type="button" class="btn small" (click)="go(1)" [disabled]="page() >= pages()" aria-label="Next page">Next</button>
    </div>
    <div class="sheet" [class.loading]="state() === 'loading'">
      @if (state() === 'error') {
        <p class="failed" role="alert">
          This page cannot be shown. The document is kept for a short time only, so it may have expired.
        </p>
      }
      <img
        [src]="src()"
        [alt]="'Page ' + page() + ' of ' + pages() + ' of the uploaded document'"
        [hidden]="state() === 'error'"
        (load)="state.set('ready')"
        (error)="state.set('error')"
      />
    </div>
  `,
  styles: `
    :host { display: grid; gap: 10px; }
    .bar { display: flex; gap: 10px; align-items: center; justify-content: space-between; }
    .count { font-size: 13px; color: var(--muted); }
    .sheet { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 8px; min-height: 240px; }
    .sheet.loading { background: linear-gradient(90deg, var(--surface), var(--bg), var(--surface)); background-size: 200% 100%; animation: shimmer 1.4s linear infinite; }
    img { display: block; width: 100%; height: auto; border-radius: 4px; background: #fff; }
    .failed { margin: 16px; color: var(--bad); font-size: 14px; }
    @keyframes shimmer { to { background-position: -200% 0; } }
  `,
})
export class PageViewer {
  readonly documentId = input.required<string>();
  readonly pages = input.required<number>();

  private readonly api = inject(ApiClient);

  /** Starts at page 1 again whenever a different document is shown. */
  protected readonly page = linkedSignal({ source: this.documentId, computation: () => 1 });
  protected readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  protected readonly src = computed(() => this.api.pageUrl(this.documentId(), this.page()));

  protected go(delta: number): void {
    const next = Math.min(Math.max(this.page() + delta, 1), this.pages());
    if (next === this.page()) return;
    this.state.set('loading');
    this.page.set(next);
  }
}
