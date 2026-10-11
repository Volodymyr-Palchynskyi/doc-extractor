import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const BASE = process.env.BASE_URL;
const OUT = '/out';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 1.5, colorScheme: 'light', acceptDownloads: true });
const page = await ctx.newPage();
const problems = [];
page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
page.on('console', (m) => { if (m.type() === 'error') problems.push('console: ' + m.text()); });

const step = (name) => console.log('OK  ' + name);

// 1. start screen
await page.goto(BASE, { waitUntil: 'networkidle' });
await page.getByText('Demo mode').first().waitFor();
assert.equal(await page.locator('.sample').count(), 3);
await page.screenshot({ path: `${OUT}/01-start.png` });
step('start screen: demo notice and 3 samples');

// 2. a document that is not a bundled sample is refused with a clear message (demo mode)
await page.locator('input[type=file]').setInputFiles('/data/dev-easy-01.pdf');
await page.getByText('Demo mode only accepts the bundled sample documents').waitFor({ timeout: 15000 });
step('non-sample upload refused with a readable message');

// 3. the German sample: wrong total
await page.locator('.sample', { hasText: 'German invoice' }).getByRole('button', { name: 'Use this sample' }).click();
await page.getByText('Needs review').waitFor({ timeout: 20000 });
await page.locator('app-page-viewer img').waitFor();
await page.waitForFunction(() => { const i = document.querySelector('app-page-viewer img'); return i && i.complete && i.naturalWidth > 0; });
const issueText = await page.locator('.issue').first().innerText();
assert.match(issueText, /total_mismatch|total/i);
assert.equal(await page.locator('#f-total').inputValue(), '28837.35');
// dates are shown in ISO form, never in the browser's locale
assert.equal(await page.locator('#f-issue-date').inputValue(), '2026-08-04');
assert.equal(await page.locator('#f-issue-date').getAttribute('placeholder'), 'YYYY-MM-DD');
await page.screenshot({ path: `${OUT}/02-needs-review.png` });
step('review screen: page image, extracted fields, total_mismatch issue');

// 4. clicking the issue focuses the field
await page.locator('.issue').first().click();
assert.equal(await page.evaluate(() => document.activeElement?.id), 'f-total');
step('clicking an issue focuses its field');

// 5. fix the total using the number the validator itself computed
const expected = /= ([\d.]+), but/.exec(issueText)?.[1];
assert.ok(expected, 'could not read the expected total from the issue message');
await page.locator('#f-total').fill(expected);
await page.getByText('Looks consistent').waitFor({ timeout: 8000 });
assert.ok(await page.getByText('edited').first().isVisible());
await page.evaluate(() => window.scrollTo(0, 0)); // show the green summary, not just the field that was edited
await page.waitForTimeout(300);
await page.screenshot({ path: `${OUT}/03-fixed.png` });
step(`edited total to ${expected}: re-check turned the summary green`);

// 6. the corrected values are what gets exported
const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export JSON' }).click()]);
const exported = JSON.parse(readFileSync(await download.path(), 'utf8'));
assert.equal(exported.total, Number(expected));
assert.equal(exported.invoice_number, 'RE-2026-5687');
const [csvDownload] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export line items (CSV)' }).click()]);
const csv = readFileSync(await csvDownload.path(), 'utf8');
assert.ok(csv.startsWith('description,quantity,unit_price,line_total\n'));
assert.equal(csv.trim().split('\n').length, 22); // header + 21 lines
step('JSON export holds the corrected total; CSV has header + 21 lines');

// 7. an unreadable number blocks export and is reported at the field
await page.locator('#f-total').fill('12abc');
// shown twice on purpose: in the issue list and next to the field
await page.locator('#f-total-messages').getByText('"12abc" is not a number.').waitFor();
await page.locator('.issue', { hasText: '"12abc" is not a number.' }).waitFor();
assert.equal(await page.getByRole('button', { name: 'Export JSON' }).isDisabled(), true);
step('unreadable number reported at the field and export disabled');

// 8. undo edits, then check another document and delete the server copy
await page.getByRole('button', { name: 'Undo my edits' }).click();
// The summary already says "Needs review" while the number is unreadable, so wait for the field itself.
await page.waitForFunction(() => document.querySelector('#f-total')?.value === '28837.35');
await page.locator('.issue', { hasText: 'Subtotal' }).waitFor();
assert.equal(await page.getByRole('button', { name: 'Undo my edits' }).count(), 0);
step('undo restores the extraction');
await page.getByRole('button', { name: 'Check another document' }).click();
await page.locator('.sample').first().waitFor();

// 9. the two-page French sample: page navigation
await page.locator('.sample', { hasText: 'French invoice' }).getByRole('button', { name: 'Use this sample' }).click();
await page.getByText('Page 1 of 2').waitFor({ timeout: 20000 });
await page.getByRole('button', { name: 'Next page' }).click();
await page.getByText('Page 2 of 2').waitFor();
await page.waitForFunction(() => { const i = document.querySelector('app-page-viewer img'); return i && i.complete && i.naturalWidth > 0; });
assert.match(await page.locator('app-page-viewer img').getAttribute('src'), /pages\/2\.png$/);
await page.screenshot({ path: `${OUT}/04-two-pages.png` });
step('two-page document: next page loads');

await browser.close();
console.log(problems.length ? 'BROWSER PROBLEMS:\n' + problems.join('\n') : 'no browser console errors');
