import { Injectable, OnDestroy, computed, inject, signal } from '@angular/core';
import { ApiClient } from './api-client';
import {
  FormState, LineProp, ScalarKey, addLine, changedKeys, fromInvoice, issuesByField, removeLine, setLine,
  setScalar, sortIssues, toInvoice,
} from './invoice-form';
import { ExtractionResult, InvoiceExtraction, Issue } from './models';

/** Wait for a pause in typing before asking the server, so one re-check follows a burst of edits. */
export const RECHECK_DELAY_MS = 500;

/**
 * State of one document under review: what the model extracted, what the human has edited since, and the
 * validator's opinion of the current values.
 *
 * Two kinds of issue are merged. Client errors ("this is not a number") come from converting the typed text;
 * server issues (totals that do not add up) come from the same validator that checked the extraction.
 * Server re-checks only run when every field is readable, are debounced, and a newer check cancels an older one,
 * so a slow response can never overwrite a fresher answer.
 */
@Injectable()
export class ReviewStore implements OnDestroy {
  private readonly api = inject(ApiClient);

  readonly result = signal<ExtractionResult | null>(null);
  readonly form = signal<FormState | null>(null);
  readonly checking = signal(false);
  readonly checkError = signal<string | null>(null);

  private readonly original = signal<FormState | null>(null);
  private readonly serverIssues = signal<Issue[]>([]);
  private timer: ReturnType<typeof setTimeout> | null = null;
  private inFlight: AbortController | null = null;

  readonly conversion = computed(() => {
    const form = this.form();
    return form ? toInvoice(form) : null;
  });
  readonly issues = computed(() => sortIssues([...(this.conversion()?.errors ?? []), ...this.serverIssues()]));
  readonly issuesByField = computed(() => issuesByField(this.issues()));
  readonly errorCount = computed(() => this.issues().filter((i) => i.severity === 'error').length);
  readonly warningCount = computed(() => this.issues().filter((i) => i.severity === 'warning').length);
  readonly changed = computed(() => {
    const original = this.original();
    const form = this.form();
    return original && form ? changedKeys(original, form) : new Set<string>();
  });
  readonly edited = computed(() => this.changed().size > 0);

  load(result: ExtractionResult): void {
    this.cancelPending();
    const form = fromInvoice(result.extraction);
    this.result.set(result);
    this.original.set(form);
    this.form.set(form);
    this.serverIssues.set(result.issues);
    this.checkError.set(null);
  }

  reset(): void {
    this.cancelPending();
    this.result.set(null);
    this.original.set(null);
    this.form.set(null);
    this.serverIssues.set([]);
    this.checkError.set(null);
  }

  setScalar(key: ScalarKey, value: string): void {
    this.update((form) => setScalar(form, key, value));
  }

  setLine(index: number, prop: LineProp, value: string): void {
    this.update((form) => setLine(form, index, prop, value));
  }

  addLine(): void {
    this.update(addLine);
  }

  removeLine(index: number): void {
    this.update((form) => removeLine(form, index));
  }

  /** Throw away every edit and show the extraction as the model produced it. */
  resetEdits(): void {
    const result = this.result();
    if (result) this.load(result);
  }

  /** The values as they stand now, or null while some field cannot be read. */
  correctedInvoice(): InvoiceExtraction | null {
    return this.conversion()?.invoice ?? null;
  }

  ngOnDestroy(): void {
    this.cancelPending();
  }

  private update(change: (form: FormState) => FormState): void {
    const form = this.form();
    if (!form) return;
    this.form.set(change(form));
    this.schedule();
  }

  private schedule(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => void this.check(), RECHECK_DELAY_MS);
  }

  private async check(): Promise<void> {
    this.timer = null;
    const invoice = this.conversion()?.invoice;
    if (!invoice) return; // unreadable fields are already reported locally, nothing to ask the server

    this.inFlight?.abort();
    const controller = new AbortController();
    this.inFlight = controller;
    this.checking.set(true);
    this.checkError.set(null);
    try {
      const outcome = await this.api.validate(invoice, controller.signal);
      if (this.inFlight === controller) this.serverIssues.set(outcome.issues);
    } catch (error) {
      if (controller.signal.aborted) return; // superseded by a newer check
      this.checkError.set(error instanceof Error ? error.message : 'The re-check failed.');
    } finally {
      if (this.inFlight === controller) {
        this.inFlight = null;
        this.checking.set(false);
      }
    }
  }

  private cancelPending(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.inFlight?.abort();
    this.inFlight = null;
    this.checking.set(false);
  }
}
