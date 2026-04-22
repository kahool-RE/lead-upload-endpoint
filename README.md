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
# Lead + Message Event Schema

This package gives you the minimum viable database layer for the expired-listing system.

## Tables

### `leads`
Core lead record used by upload, scoring, filtering, and outreach.

Fields:
- `id`
- `address`
- `city`
- `state`
- `zip`
- `status`
- `price`
- `property_type`
- `dom`
- `phone`
- `email`
- `owner_name`
- `owner_occupied`
- `score`
- `outreach_status`
- `do_not_contact`
- `created_at`
- `updated_at`

### `message_events`
Append-only event log for outbound and inbound communication.

Fields:
- `id`
- `lead_id`
- `channel`
- `direction`
- `message_body`
- `sent_at`
- `received_at`
- `status`

## Recommended values

### `outreach_status`
- `new`
- `queued`
- `contacted`
- `replied`
- `qualified`
- `booked`
- `dead`
- `do_not_contact`

### `channel`
- `sms`
- `email`

### `direction`
- `outbound`
- `inbound`

### `message_events.status`
- `queued`
- `sent`
- `delivered`
- `failed`
- `received`

## Why this is enough for MVP

This schema supports:
- lead upload
- hard filtering
- rules-based scoring
- outbound SMS/email logging
- inbound reply logging
- conversation history per lead
- stop-contact logic with `do_not_contact`

## Next schema upgrades

Do not add these until the basic send/reply loop works:
- `external_message_id`
- `thread_id`
- `error_code`
- `error_message`
- `agent_id`
- `campaign_id`
- `last_contacted_at`
- `next_follow_up_at`
- `dedupe_key`
