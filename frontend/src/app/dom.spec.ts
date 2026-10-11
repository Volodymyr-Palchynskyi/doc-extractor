import { fieldId, focusField, slug } from './dom';
import { LINE_PROPS, SCALAR_KEYS, lineKey } from './invoice-form';

describe('fieldId', () => {
  it('turns control keys into valid, readable DOM ids', () => {
    expect(fieldId('total')).toBe('f-total');
    expect(fieldId('vendor.name')).toBe('f-vendor-name');
    expect(fieldId('line_items[2].line_total')).toBe('f-line-items-2-line-total');
  });

  it('gives every control of a 30-line invoice its own id', () => {
    const keys = [...SCALAR_KEYS, ...Array.from({ length: 30 }, (_, i) => LINE_PROPS.map((p) => lineKey(i, p))).flat()];

    expect(new Set(keys.map(fieldId)).size).toBe(keys.length);
  });
});

describe('focusField', () => {
  afterEach(() => (document.body.innerHTML = ''));

  it('focuses the control and reports success', () => {
    document.body.innerHTML = '<input id="f-total">';

    expect(focusField('total')).toBe(true);
    expect(document.activeElement?.id).toBe('f-total');
  });

  it('reports false for an issue that has no control of its own', () => {
    expect(focusField('line_items')).toBe(false);
  });
});

describe('slug', () => {
  it('makes safe file names and keeps non-latin letters', () => {
    expect(slug('INV-2026/001')).toBe('inv-2026-001');
    expect(slug('Рахунок №5')).toBe('рахунок-5');
  });

  it('falls back when nothing usable is left and limits the length', () => {
    expect(slug('???')).toBe('invoice');
    expect(slug('???', 'x')).toBe('x');
    expect(slug('a'.repeat(200)).length).toBe(60);
  });
});
