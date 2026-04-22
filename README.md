# Lead Upload Endpoint

## Route

`POST /api/v1/leads/upload`

Multipart form-data:
- `file`: `.csv`, `.xlsx`, or `.xls`
- `dry_run`: `true|false` (default `true`)
- `preview_limit`: integer (default `20`)

## Example curl

```bash
curl -X POST "http://localhost:8000/api/v1/leads/upload?dry_run=true&preview_limit=10" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@Sample listings.xls"
```

## What it does

- accepts the uploaded lead file
- parses `.csv`, `.xlsx`, and `.xls`
- for `.xls`, falls back to LibreOffice conversion if direct parsing is unavailable
- validates required columns
- normalizes core real-estate lead fields
- picks the best non-DNC phone number
- builds a stable dedupe key
- supports dry-run preview before database write

## Next integration step

Replace the placeholder `get_db()` and `Lead` model wiring with your real SQLAlchemy session and model.


## New filtering and scoring behavior

The upload pipeline now applies hard filters and deterministic scoring.

### Hard filters
Rows are rejected when any of the following is true:
- `Status != Expired`
- no valid phone and no valid email
- `Contact Phone DNC == Yes`
- `Days On Market < 30`

### Priority buckets
Rows that pass hard filters are still bucketed:
- `high` priority: score >= 70
- `low` priority: score < 70

### Scoring
- `+50` expired
- `+20` DOM > 60
- `+15` owner occupied
- `+10` price inside target band
- `-30` DNC
- `-20` missing contact channel

### Endpoint params
- `target_price_min`: optional numeric lower bound for price-band bonus
- `target_price_max`: optional numeric upper bound for price-band bonus

Example:
```bash
curl -X POST "http://localhost:8000/api/v1/leads/upload?dry_run=true&target_price_min=700000&target_price_max=1200000"   -F "file=@Sample listings.xls"
```
