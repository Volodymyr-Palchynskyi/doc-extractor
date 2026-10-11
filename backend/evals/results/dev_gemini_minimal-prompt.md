_Generated 2026-10-11 15:10 UTC_

# Extraction eval: dev split, extractor `gemini`, model `gemini-3.7-flash`

- exact: every scored field and every line item right
- fields: share of scalar fields right; items: share of line items fully right
- false alarms: consistent document, but the extraction made the validator complain (an extraction error)
- missed: document inconsistent as printed, but the extraction came out consistent (the model 'fixed' it)

| slice | docs | exact | fields | items | false alarms | missed / printed errors |
|---|---|---|---|---|---|---|
| all | 28 | 86% | 98% | 100% | 0 | 0/5 |
| easy | 8 | 62% | 95% | 100% | 0 | 0/0 |
| medium | 10 | 100% | 100% | 100% | 0 | 0/2 |
| hard | 10 | 90% | 98% | 100% | 0 | 0/3 |

## Accuracy per field

| field | accuracy |
|---|---|
| invoice_number | 100% |
| issue_date | 100% |
| due_date | 100% |
| currency | 100% |
| vendor_name | 100% |
| buyer_name | 100% |
| vendor_tax_id | 89% |
| buyer_tax_id | 86% |
| subtotal | 100% |
| discount_total | 100% |
| tax_total | 100% |
| total | 100% |

## Cost and latency

| docs | mean latency | mean tokens | total tokens |
|---|---|---|---|
| 28 | 10.1s | 2,030 | 56,852 |

## Documents that were not exact

- `dev-easy-00` (modern, en_US): fields: buyer_tax_id
- `dev-easy-04` (modern, en_US): fields: vendor_tax_id, buyer_tax_id
- `dev-easy-05` (modern, en_US): fields: vendor_tax_id, buyer_tax_id
- `dev-hard-02` (classic, en_US): fields: vendor_tax_id, buyer_tax_id
