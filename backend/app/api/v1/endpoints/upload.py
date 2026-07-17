from fastapi import UploadFile, APIRouter, Depends, File, Form, Body, Path as RequestPath
from app.services.upload_service import UploadService
from app.schemas import upload_schema
from app.schemas.upload_schema import InitUploadResponse, UploadStatusResponse, MergeChunksResponse
from app.db.session import get_session
from sqlmodel.ext.asyncio.session import AsyncSession


router = APIRouter()


@router.post("/init", response_model=upload_schema.InitUploadResponse)
async def init_upload(
        upload_info: upload_schema.InitUploadRequest,
        upload_service: UploadService = Depends()
):
    upload_session = await upload_service.init_file_upload(
        upload_info.file_name,
        upload_info.file_hash,
        upload_info.file_ext,
        upload_info.mime_type,
        upload_info.total_size,
        upload_info.chunk_size,
        upload_info.total_chunks
    )
    return InitUploadResponse(
        upload_id = upload_session.upload_id
    )

@router.post("/{upload_id}/chunk")
async def upload_chunk(
        upload_id: str = RequestPath(...),
        chunk_index: int = Form(...),
        chunk_file: UploadFile = File(...),
        upload_service: UploadService = Depends()
):
    await upload_service.upload_file_chunk(
        upload_id=upload_id,
        chunk_index=chunk_index,
        chunk_file=chunk_file
    )

@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
        upload_id: str = RequestPath(...),
        upload_service: UploadService = Depends()
):
    upload_session = await upload_service.get_status(
        upload_id=upload_id
    )
    return UploadStatusResponse(
        upload_id = upload_session.upload_id,
        uploaded_chunks = upload_session.uploaded_chunks,
        total_chunks = upload_session.total_chunks
    )


@router.post("/{upload_id}/merge", response_model=MergeChunksResponse)
async def merge_chunks(
        upload_id: str = RequestPath(...),
        upload_service: UploadService = Depends(),
        db: AsyncSession = Depends(get_session)
):
    file_records = await upload_service.merge_chunks(
        upload_id=upload_id,
        db=db
    )
    return MergeChunksResponse(
        status="success",
        file_record_id=file_records.id,
        storage_key=str(file_records.storage_key)
    )


