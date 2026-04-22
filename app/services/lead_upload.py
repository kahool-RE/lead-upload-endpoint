from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException, UploadFile

from app.schemas.lead_upload import LeadUploadLeadPreview, LeadUploadResponse, LeadUploadRowError

ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}
REQUIRED_COLUMNS = {'Address', 'City', 'State'}
PHONE_COLUMNS = [
    'Contact Phone',
    'User Phone 1',
    'User Phone 2',
    'Basic Phone1',
    'Basic Phone2',
    'Augmented Phone 1_1',
    'Augmented Phone 1_2',
    'Augmented Phone 2_1',
    'Augmented Phone 2_2',
    'Augmented Phone 3_1',
    'Augmented Phone 3_2',
    'Augmented Phone 4_1',
    'Augmented Phone 4_2',
    'List Agent Phone',
]
EMAIL_COLUMNS = [
    'List Agent Email',
    'Augmented Email 1_1',
    'Augmented Email 1_2',
    'Augmented Email 1_3',
    'Augmented Email 2_1',
    'Augmented Email 2_2',
    'Augmented Email 2_3',
    'Augmented Email 3_1',
    'Augmented Email 3_2',
    'Augmented Email 3_3',
    'Augmented Email 4_1',
    'Augmented Email 4_2',
    'Augmented Email 4_3',
]
DNC_LOOKUP = {
    'Contact Phone': 'Contact Phone DNC',
    'Augmented Phone 1_1': 'Augmented Phone 1_1 DNC',
    'Augmented Phone 1_2': 'Augmented Phone 1_2 DNC',
    'Augmented Phone 2_1': 'Augmented Phone 2_1 DNC',
    'Augmented Phone 2_2': 'Augmented Phone 2_2 DNC',
    'Augmented Phone 3_1': 'Augmented Phone 3_1 DNC',
    'Augmented Phone 3_2': 'Augmented Phone 3_2 DNC',
    'Augmented Phone 4_1': 'Augmented Phone 4_1 DNC',
    'Augmented Phone 4_2': 'Augmented Phone 4_2 DNC',
}
SCORING_RULES = {
    'expired': 50,
    'dom_gt_60': 20,
    'owner_occupied': 15,
    'target_price_band': 10,
    'dnc_penalty': -30,
    'missing_contact_channel_penalty': -20,
}
FILTER_RULES = [
    'Status must equal Expired',
    'Phone or email must exist',
    'Contact Phone DNC must not be Yes',
    'Days On Market must be at least 30',
]


@dataclass
class ParsedUpload:
    total_rows: int
    accepted_rows: int
    low_priority_rows: int
    rejected_rows: int
    status_breakdown: dict[str, int]
    preview: list[LeadUploadLeadPreview]
    errors: list[LeadUploadRowError]
    rows_for_db: list[dict[str, Any]]


class LeadUploadService:
    def __init__(self, db_session: Any | None = None):
        self.db = db_session

    async def handle_upload(
        self,
        file: UploadFile,
        dry_run: bool = True,
        preview_limit: int = 20,
        target_price_min: float | None = None,
        target_price_max: float | None = None,
    ) -> LeadUploadResponse:
        ext = Path(file.filename or '').suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f'Unsupported file type: {ext}. Allowed: {sorted(ALLOWED_EXTENSIONS)}')

        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail='Uploaded file is empty.')

        df = self._load_dataframe(contents=contents, filename=file.filename or f'upload{ext}')
        parsed = self._parse_dataframe(
            df=df,
            preview_limit=preview_limit,
            target_price_min=target_price_min,
            target_price_max=target_price_max,
        )

        inserted = 0
        updated = 0
        skipped_duplicates = 0
        mode = 'dry_run' if dry_run else 'commit'

        if not dry_run:
            inserted, updated, skipped_duplicates = self._persist_rows(parsed.rows_for_db)

        return LeadUploadResponse(
            mode=mode,
            filename=file.filename or 'upload',
            total_rows=parsed.total_rows,
            accepted_rows=parsed.accepted_rows,
            low_priority_rows=parsed.low_priority_rows,
            rejected_rows=parsed.rejected_rows,
            inserted=inserted,
            updated=updated,
            skipped_duplicates=skipped_duplicates,
            status_breakdown=parsed.status_breakdown,
            preview=parsed.preview,
            errors=parsed.errors,
            scoring_rules=SCORING_RULES,
            filter_rules=FILTER_RULES,
        )

    def _load_dataframe(self, contents: bytes, filename: str) -> pd.DataFrame:
        ext = Path(filename).suffix.lower()
        if ext == '.csv':
            return self._read_csv(contents)
        if ext == '.xlsx':
            return self._read_xlsx(contents)
        if ext == '.xls':
            return self._read_xls(contents, filename)
        raise HTTPException(status_code=400, detail=f'Unsupported file type: {ext}')

    def _read_csv(self, contents: bytes) -> pd.DataFrame:
        try:
            return pd.read_csv(io.BytesIO(contents), dtype=str).fillna('')
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(contents), dtype=str, encoding='latin1').fillna('')
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f'Could not read CSV file: {exc}') from exc

    def _read_xlsx(self, contents: bytes) -> pd.DataFrame:
        try:
            return pd.read_excel(io.BytesIO(contents), dtype=str).fillna('')
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f'Could not read XLSX file: {exc}') from exc

    def _read_xls(self, contents: bytes, filename: str) -> pd.DataFrame:
        try:
            return pd.read_excel(io.BytesIO(contents), dtype=str).fillna('')
        except Exception:
            pass

        libreoffice = shutil.which('libreoffice') or shutil.which('soffice')
        if not libreoffice:
            raise HTTPException(
                status_code=400,
                detail='Could not read .xls file. Install xlrd or LibreOffice in the API container.',
            )

        with tempfile.TemporaryDirectory(prefix='lead-upload-') as tmpdir:
            src_path = os.path.join(tmpdir, filename)
            out_dir = os.path.join(tmpdir, 'out')
            os.makedirs(out_dir, exist_ok=True)
            with open(src_path, 'wb') as f:
                f.write(contents)
            cmd = [libreoffice, '--headless', '--convert-to', 'csv', '--outdir', out_dir, src_path]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                raise HTTPException(status_code=400, detail=f'LibreOffice failed to convert .xls: {proc.stderr or proc.stdout}')
            csv_path = os.path.join(out_dir, f'{Path(filename).stem}.csv')
            if not os.path.exists(csv_path):
                raise HTTPException(status_code=400, detail='LibreOffice conversion completed but CSV output was not found.')
            with open(csv_path, 'rb') as f:
                csv_bytes = f.read()
            return self._read_csv(csv_bytes)

    def _parse_dataframe(
        self,
        df: pd.DataFrame,
        preview_limit: int,
        target_price_min: float | None,
        target_price_max: float | None,
    ) -> ParsedUpload:
        df.columns = [str(c).strip() for c in df.columns]
        missing = sorted(col for col in REQUIRED_COLUMNS if col not in df.columns)
        if missing:
            raise HTTPException(status_code=400, detail=f'Missing required columns: {missing}')

        total_rows = len(df)
        preview: list[LeadUploadLeadPreview] = []
        errors: list[LeadUploadRowError] = []
        rows_for_db: list[dict[str, Any]] = []
        status_breakdown: dict[str, int] = {}
        seen_dedupe_keys: set[str] = set()
        accepted_rows = 0
        low_priority_rows = 0

        for index, raw in df.iterrows():
            row_number = index + 2
            row = {k: self._clean(raw.get(k)) for k in df.columns}
            status = (row.get('Status') or '').strip()
            if status:
                status_breakdown[status] = status_breakdown.get(status, 0) + 1

            try:
                normalized = self._normalize_row(row, target_price_min=target_price_min, target_price_max=target_price_max)
                if not normalized['address']:
                    raise ValueError('Address is required.')
                if normalized['dedupe_key'] in seen_dedupe_keys:
                    continue
                seen_dedupe_keys.add(normalized['dedupe_key'])

                if normalized['rule_outcome'] == 'rejected':
                    errors.append(
                        LeadUploadRowError(
                            row_number=row_number,
                            message='Rejected by hard filter rules.',
                            listing_id=normalized.get('external_listing_id'),
                            address=normalized.get('address'),
                            rule_outcome='rejected',
                            reasons=normalized.get('rule_reasons', []),
                        )
                    )
                    continue

                rows_for_db.append(normalized)
                if normalized['priority'] == 'high':
                    accepted_rows += 1
                else:
                    low_priority_rows += 1
                    errors.append(
                        LeadUploadRowError(
                            row_number=row_number,
                            message='Accepted but marked low priority.',
                            listing_id=normalized.get('external_listing_id'),
                            address=normalized.get('address'),
                            rule_outcome='low_priority',
                            reasons=normalized.get('rule_reasons', []),
                        )
                    )

                if len(preview) < preview_limit:
                    preview.append(LeadUploadLeadPreview(**normalized))
            except Exception as exc:
                errors.append(
                    LeadUploadRowError(
                        row_number=row_number,
                        message=str(exc),
                        listing_id=self._clean(row.get('Listing ID')),
                        address=self._clean(row.get('Address')),
                        rule_outcome='rejected',
                    )
                )

        rejected_rows = sum(1 for e in errors if e.rule_outcome == 'rejected')
        return ParsedUpload(
            total_rows=total_rows,
            accepted_rows=accepted_rows,
            low_priority_rows=low_priority_rows,
            rejected_rows=rejected_rows,
            status_breakdown=status_breakdown,
            preview=preview,
            errors=errors[:200],
            rows_for_db=rows_for_db,
        )

    def _normalize_row(
        self,
        row: dict[str, str],
        target_price_min: float | None,
        target_price_max: float | None,
    ) -> dict[str, Any]:
        address = self._clean(row.get('Address'))
        city = self._clean(row.get('City'))
        state = self._clean(row.get('State'))
        zip_code = self._digits_only(row.get('Zip'), max_len=5)
        owner_name = self._first_non_empty(row.get('Owner Name1'), row.get('Owner Name2'))
        contact_name = self._first_non_empty(
            row.get('Owner First Name'),
            row.get('Basic Name1'),
            row.get('Augmented Name 1'),
            row.get('Borrower Name'),
        )
        best_phone = self._pick_best_phone(row)
        best_email = self._pick_best_email(row)
        external_listing_id = self._clean(row.get('Listing ID'))
        mls_number = self._clean(row.get('MLS Number'))
        source = self._clean(row.get('Source')) or 'upload'
        status = self._clean(row.get('Status'))
        days_on_market = self._to_int(row.get('Days On Market'))
        owner_occupied = self._to_bool(row.get('Owner Occupied'))
        contact_phone_dnc = self._to_bool(row.get('Contact Phone DNC'))
        price = self._to_float(row.get('Price'))
        dedupe_key = self._build_dedupe_key(external_listing_id, mls_number, address, city, state, zip_code)

        score = self._score_row(
            status=status,
            days_on_market=days_on_market,
            owner_occupied=owner_occupied,
            price=price,
            contact_phone_dnc=contact_phone_dnc,
            has_contact_channel=bool(best_phone or best_email),
            target_price_min=target_price_min,
            target_price_max=target_price_max,
        )
        rule_outcome, rule_reasons, priority = self._apply_rules(
            status=status,
            days_on_market=days_on_market,
            contact_phone_dnc=contact_phone_dnc,
            has_contact_channel=bool(best_phone or best_email),
            score=score,
        )

        normalized = {
            'external_listing_id': external_listing_id,
            'status': status,
            'address': address,
            'city': city,
            'state': state,
            'zip_code': zip_code,
            'county': self._clean(row.get('County')),
            'price': price,
            'bedrooms': self._to_float(row.get('Bedrooms') or row.get('Tax Beds')),
            'bathrooms': self._to_float(row.get('Bathrooms') or row.get('Tax Baths')),
            'square_footage': self._to_int(row.get('Square Footage') or row.get('Tax Square Footage')),
            'lot_size': self._to_float(row.get('Lot Size') or row.get('Tax Lot')),
            'year_built': self._to_int(row.get('Year Built')),
            'property_type': self._clean(row.get('Property type')),
            'owner_name': owner_name,
            'owner_occupied': owner_occupied,
            'contact_name': contact_name,
            'best_phone': best_phone,
            'best_email': best_email,
            'list_agent_name': self._clean(row.get('List Agent Name')),
            'list_agent_email': self._clean(row.get('List Agent Email')),
            'list_agent_phone': self._normalize_phone(row.get('List Agent Phone')),
            'listing_office_name': self._clean(row.get('Listing Office Name')),
            'mls_number': mls_number,
            'source': source,
            'source_url': self._clean(row.get('Source URL')),
            'processed_at': self._parse_datetime(row.get('Processed Date')),
            'days_on_market': days_on_market,
            'apn': self._clean(row.get('APN')),
            'remarks': self._clean(row.get('Remarks/Ad Text')),
            'score': score,
            'priority': priority,
            'rule_outcome': rule_outcome,
            'rule_reasons': rule_reasons,
            'dedupe_key': dedupe_key,
        }
        return normalized

    def _apply_rules(
        self,
        status: str | None,
        days_on_market: int | None,
        contact_phone_dnc: bool | None,
        has_contact_channel: bool,
        score: int,
    ) -> tuple[str, list[str], str]:
        reasons: list[str] = []
        if (status or '').strip().lower() != 'expired':
            reasons.append('status_not_expired')
        if not has_contact_channel:
            reasons.append('missing_contact_channel')
        if contact_phone_dnc is True:
            reasons.append('contact_phone_dnc_yes')
        if days_on_market is None or days_on_market < 30:
            reasons.append('days_on_market_below_30')

        if reasons:
            return 'rejected', reasons, 'low'

        priority = 'high' if score >= 70 else 'low'
        low_priority_reasons: list[str] = []
        if priority == 'low':
            low_priority_reasons.append('score_below_high_priority_threshold')
        return 'accepted' if priority == 'high' else 'low_priority', low_priority_reasons, priority

    def _score_row(
        self,
        status: str | None,
        days_on_market: int | None,
        owner_occupied: bool | None,
        price: float | None,
        contact_phone_dnc: bool | None,
        has_contact_channel: bool,
        target_price_min: float | None,
        target_price_max: float | None,
    ) -> int:
        score = 0
        if (status or '').strip().lower() == 'expired':
            score += SCORING_RULES['expired']
        if days_on_market is not None and days_on_market > 60:
            score += SCORING_RULES['dom_gt_60']
        if owner_occupied is True:
            score += SCORING_RULES['owner_occupied']
        if self._in_target_price_band(price=price, target_price_min=target_price_min, target_price_max=target_price_max):
            score += SCORING_RULES['target_price_band']
        if contact_phone_dnc is True:
            score += SCORING_RULES['dnc_penalty']
        if not has_contact_channel:
            score += SCORING_RULES['missing_contact_channel_penalty']
        return score

    def _in_target_price_band(self, price: float | None, target_price_min: float | None, target_price_max: float | None) -> bool:
        if price is None:
            return False
        if target_price_min is not None and price < target_price_min:
            return False
        if target_price_max is not None and price > target_price_max:
            return False
        if target_price_min is None and target_price_max is None:
            return False
        return True

    def _pick_best_phone(self, row: dict[str, str]) -> str | None:
        for column in PHONE_COLUMNS:
            raw = self._clean(row.get(column))
            if not raw:
                continue
            dnc_col = DNC_LOOKUP.get(column)
            if dnc_col and self._to_bool(row.get(dnc_col)) is True:
                continue
            normalized = self._normalize_phone(raw)
            if normalized:
                return normalized
        return None

    def _pick_best_email(self, row: dict[str, str]) -> str | None:
        for column in EMAIL_COLUMNS:
            value = self._clean(row.get(column))
            if value and '@' in value:
                return value.lower()
        return None

    def _persist_rows(self, rows: list[dict[str, Any]]) -> tuple[int, int, int]:
        if self.db is None or Lead is None:
            return len(rows), 0, 0

        inserted = 0
        updated = 0
        skipped_duplicates = 0

        for row in rows:
            existing = self.db.query(Lead).filter(Lead.dedupe_key == row['dedupe_key']).one_or_none()
            if existing is None:
                self.db.add(Lead(**row))
                inserted += 1
                continue
            changed = False
            for key, value in row.items():
                current = getattr(existing, key, None)
                if value not in (None, '', []) and current != value:
                    setattr(existing, key, value)
                    changed = True
            if changed:
                updated += 1
            else:
                skipped_duplicates += 1

        self.db.commit()
        return inserted, updated, skipped_duplicates

    def _build_dedupe_key(self, listing_id: str | None, mls_number: str | None, address: str | None, city: str | None, state: str | None, zip_code: str | None) -> str:
        base = '|'.join([
            (listing_id or '').strip().lower(),
            (mls_number or '').strip().lower(),
            (address or '').strip().lower(),
            (city or '').strip().lower(),
            (state or '').strip().lower(),
            (zip_code or '').strip().lower(),
        ])
        return hashlib.sha256(base.encode('utf-8')).hexdigest()

    def _clean(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, float) and pd.isna(value):
            return None
        text = str(value).strip()
        if not text or text.lower() in {'nan', 'none', 'null'}:
            return None
        return text

    def _to_float(self, value: Any) -> float | None:
        text = self._clean(value)
        if text is None:
            return None
        text = text.replace('$', '').replace(',', '').strip()
        try:
            return float(text)
        except ValueError:
            return None

    def _to_int(self, value: Any) -> int | None:
        number = self._to_float(value)
        return int(number) if number is not None else None

    def _to_bool(self, value: Any) -> bool | None:
        text = (self._clean(value) or '').lower()
        if text in {'y', 'yes', 'true', '1'}:
            return True
        if text in {'n', 'no', 'false', '0'}:
            return False
        return None

    def _parse_datetime(self, value: Any) -> datetime | None:
        text = self._clean(value)
        if not text:
            return None
        for fmt in ('%m/%d/%Y %H:%M:%S', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
        return None

    def _normalize_phone(self, value: Any) -> str | None:
        text = self._clean(value)
        if not text:
            return None
        digits = re.sub(r'\D', '', text)
        if len(digits) == 11 and digits.startswith('1'):
            digits = digits[1:]
        if len(digits) != 10:
            return None
        return f'+1{digits}'

    def _digits_only(self, value: Any, max_len: int | None = None) -> str | None:
        text = self._clean(value)
        if not text:
            return None
        digits = re.sub(r'\D', '', text)
        if max_len:
            digits = digits[:max_len]
        return digits or None

    def _first_non_empty(self, *values: Any) -> str | None:
        for value in values:
            cleaned = self._clean(value)
            if cleaned:
                return cleaned
        return None


try:
    from app.models.lead import Lead
except Exception:
    Lead = None
