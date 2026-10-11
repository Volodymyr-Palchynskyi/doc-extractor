/** Stable DOM id for a control key such as 'line_items[2].line_total' (so issues can find their input). */
export const fieldId = (key: string): string => 'f-' + key.replace(/[^a-zA-Z0-9]+/g, '-').replace(/-+$/, '');

/** Scroll a control into view and focus it. Returns false if there is no such control (e.g. an issue on 'line_items'). */
export function focusField(key: string): boolean {
  const element = document.getElementById(fieldId(key));
  if (!element) return false;
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  element.scrollIntoView?.({ block: 'center', behavior: reduceMotion ? 'auto' : 'smooth' }); // absent in jsdom
  element.focus({ preventScroll: true });
  return true;
}

/** Hand the user a file without a server round trip. */
export function downloadFile(name: string, content: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: `${mime};charset=utf-8` }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

/** "Acme GmbH / INV-001" -> "acme-gmbh-inv-001", for download names. */
export function slug(text: string, fallback = 'invoice'): string {
  const cleaned = text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-+|-+$/g, '').slice(0, 60);
  return cleaned || fallback;
}
