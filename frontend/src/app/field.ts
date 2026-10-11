import { ChangeDetectionStrategy, Component, booleanAttribute, computed, input, output } from '@angular/core';
import { fieldId } from './dom';
import { Issue } from './models';

/**
 * Dates are plain text in ISO form, not the browser's date picker: a picker shows the date in the browser's
 * locale (08/04/2026), which on a tool that checks invoices from several countries invites exactly the
 * day-first / month-first mistake the data is full of.
 *
 * One labelled input with its validation messages. The key is the backend's issue path, so the same string
 * links an issue to this control, marks it as edited, and gives it a DOM id the issue list can focus.
 */
@Component({
  selector: 'app-field',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <label class="field" [class.compact]="compact()" [class.has-error]="hasError()" [class.has-warning]="!hasError() && issues().length > 0" [class.edited]="changed()">
      @if (!compact()) {
        <span class="label">
          {{ label() }}
          @if (changed()) { <span class="edited-badge">edited</span> }
        </span>
      }
      <input
        [id]="id()"
        type="text"
        [attr.inputmode]="kind() === 'numeric' ? 'decimal' : kind() === 'date' ? 'numeric' : null"
        [attr.placeholder]="kind() === 'date' ? 'YYYY-MM-DD' : null"
        [value]="value()"
        (input)="valueChange.emit($any($event.target).value)"
        [attr.aria-label]="compact() ? label() : null"
        [attr.aria-invalid]="hasError() ? 'true' : null"
        [attr.aria-describedby]="issues().length ? id() + '-messages' : null"
        autocomplete="off"
      />
    </label>
    @if (issues().length) {
      <ul class="messages" [id]="id() + '-messages'">
        @for (issue of issues(); track $index) {
          <li [class]="issue.severity">{{ issue.message }}</li>
        }
      </ul>
    }
  `,
  styles: `
    :host { display: block; min-width: 0; }
    .field { display: grid; gap: 4px; }
    .label { font-size: 12px; font-weight: 600; color: var(--muted); display: flex; gap: 6px; align-items: center; }
    .edited-badge { font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em; padding: 1px 6px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); }
    input { font: inherit; color: inherit; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 7px 9px; width: 100%; box-sizing: border-box; }
    input:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
    .edited input { border-color: var(--accent); }
    .has-error input { border-color: var(--bad); background: var(--bad-soft); }
    .has-warning input { border-color: var(--warn); background: var(--warn-soft); }
    .compact input { padding: 5px 7px; font-size: 13px; }
    .messages { list-style: none; margin: 4px 0 0; padding: 0; font-size: 12px; line-height: 1.4; }
    .messages .error { color: var(--bad); }
    .messages .warning { color: var(--warn); }
  `,
})
export class Field {
  readonly key = input.required<string>();
  readonly label = input.required<string>();
  readonly value = input.required<string>();
  readonly kind = input<'text' | 'numeric' | 'date'>('text');
  readonly issues = input<Issue[]>([]);
  readonly changed = input(false, { transform: booleanAttribute });
  readonly compact = input(false, { transform: booleanAttribute });
  readonly valueChange = output<string>();

  protected readonly id = computed(() => fieldId(this.key()));
  protected readonly hasError = computed(() => this.issues().some((i) => i.severity === 'error'));
}
