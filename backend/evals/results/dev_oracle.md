_Generated 2026-10-10 18:08 UTC_

# Extraction eval: dev split, extractor `oracle`

- exact: every scored field and every line item right
- fields: share of scalar fields right; items: share of line items fully right
- false alarms: consistent document, but the extraction made the validator complain (an extraction error)
- missed: document inconsistent as printed, but the extraction came out consistent (the model 'fixed' it)

| slice | docs | exact | fields | items | false alarms | missed / printed errors |
|---|---|---|---|---|---|---|
| all | 28 | 100% | 100% | 100% | 0 | 0/5 |
| easy | 8 | 100% | 100% | 100% | 0 | 0/0 |
| medium | 10 | 100% | 100% | 100% | 0 | 0/2 |
| hard | 10 | 100% | 100% | 100% | 0 | 0/3 |

## Accuracy per field

| field | accuracy |
|---|---|
| invoice_number | 100% |
| issue_date | 100% |
| due_date | 100% |
| currency | 100% |
| vendor_name | 100% |
| buyer_name | 100% |
| vendor_tax_id | 100% |
| buyer_tax_id | 100% |
| subtotal | 100% |
| discount_total | 100% |
| tax_total | 100% |
| total | 100% |
