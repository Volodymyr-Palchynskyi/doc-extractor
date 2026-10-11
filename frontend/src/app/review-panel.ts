import { DecimalPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { downloadFile, focusField, slug } from './dom';
import { Field } from './field';
import { LineProp, ScalarKey, lineItemsToCsv, lineKey } from './invoice-form';
import { Issue } from './models';
import { ReviewStore } from './review-store';

@Component({
  selector: 'app-review-panel',
  imports: [Field, DecimalPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './review-panel.html',
  styleUrl: './review-panel.scss',
})
export class ReviewPanel {
  protected readonly store = inject(ReviewStore);

  /** True in demo mode, where the cost line describes a recorded run rather than this request. */
  readonly recorded = input(false);
  readonly newDocument = output<void>();

  protected readonly lineKey = lineKey;
  protected readonly indexes = computed(() => (this.store.form()?.lines ?? []).map((_, i) => i));
  protected readonly canExport = computed(() => this.store.correctedInvoice() !== null);

  protected value(key: ScalarKey): string {
    return this.store.form()?.fields[key] ?? '';
  }

  protected lineValue(index: number, prop: LineProp): string {
    return this.store.form()?.lines[index]?.[prop] ?? '';
  }

  protected issuesFor(key: string): Issue[] {
    return this.store.issuesByField().get(key) ?? [];
  }

  protected isChanged(key: string): boolean {
    return this.store.changed().has(key);
  }

  /** Jump to the control an issue is about. Issues about the invoice as a whole have no single control. */
  protected show(issue: Issue): void {
    focusField(issue.field);
  }

  protected exportJson(): void {
    const invoice = this.store.correctedInvoice();
    if (invoice) downloadFile(`${slug(invoice.invoice_number)}.json`, JSON.stringify(invoice, null, 2) + '\n', 'application/json');
  }

  protected exportCsv(): void {
    const invoice = this.store.correctedInvoice();
    if (invoice) downloadFile(`${slug(invoice.invoice_number)}-lines.csv`, lineItemsToCsv(invoice), 'text/csv');
  }
}
