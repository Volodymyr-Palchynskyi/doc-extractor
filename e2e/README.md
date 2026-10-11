# End-to-end browser test

`e2e.mjs` drives a real Chromium through the whole journey and fails on the first thing that is not as expected:

1. the start screen shows the demo notice and three samples
2. a document that is not a bundled sample is refused with a readable message
3. a sample with a wrong total goes through: page image, extracted fields, a `total_mismatch` issue
4. clicking an issue focuses its field
5. editing the total to the value the validator computed turns the summary green after the debounced re-check
6. the exported JSON contains the corrected total; the CSV has a header and one row per line
7. a value that is not a number is reported at its field and disables export
8. "Undo my edits" restores the extraction
9. on a two-page document, "Next page" loads page 2

It also writes the screenshots in `docs/images/`, so the pictures in the README come from the same run that proved the behaviour.

```bash
docker compose up -d --build --wait
bash e2e/run.sh
```

It needs Docker and pulls the Playwright image the first time (about 2 GB). It is not part of CI for that reason; CI runs `scripts/smoke.sh`, which covers the same API path through nginx in a few seconds.

Two real problems were found by writing this test: an nginx location rule that answered page images with a 404 because the URL ended in `.png`, and a native date picker that showed dates in the browser's locale next to a page printing them differently.
