from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.schemas.lead_upload import LeadUploadResponse
from app.services.lead_upload import LeadUploadService

router = APIRouter(prefix='/api/v1/leads', tags=['leads'])


def get_db():
    return None


@router.post('/upload', response_model=LeadUploadResponse)
async def upload_leads(
    file: UploadFile = File(...),
    dry_run: bool = True,
    preview_limit: int = 20,
    target_price_min: float | None = None,
    target_price_max: float | None = None,
    db=Depends(get_db),
):
    service = LeadUploadService(db_session=db)
    return await service.handle_upload(
        file=file,
        dry_run=dry_run,
        preview_limit=preview_limit,
        target_price_min=target_price_min,
        target_price_max=target_price_max,
    )
