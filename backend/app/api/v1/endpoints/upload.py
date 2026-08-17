import os

from fastapi import UploadFile, APIRouter, Depends, File, Form, Body, Path as RequestPath, Request, Query, status
from app.services.upload_service import UploadService
from app.schemas import upload_schema
from app.schemas.upload_schema import InitUploadResponse, UploadStatusResponse, MergeChunksResponse, \
    MergeTriggerResponse
from app.schemas.upload_schema import UploadStatus



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
        request: Request,
        upload_id: str = RequestPath(...),
        chunk_index: int = Query(...),
        upload_service: UploadService = Depends()
):
    print(f"[PID: {os.getpid()}] 接收到文件分片")
    await upload_service.upload_file_chunk(
        upload_id=upload_id,
        chunk_index=chunk_index,
        chunk_file=request.stream()
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
        status = upload_session.status,
        uploaded_chunks = upload_session.uploaded_chunks,
        total_chunks = upload_session.total_chunks,
        file_record_id = upload_session.file_record_id
    )


# @router.post("/{upload_id}/merge", response_model=MergeChunksResponse)
# async def merge_chunks(
#         upload_id: str = RequestPath(...),
#         upload_service: UploadService = Depends(),
#         db: AsyncSession = Depends(get_session)
# ):
#     file_records = await upload_service.merge_chunks(
#         upload_id=upload_id,
#         db=db
#     )
#     return MergeChunksResponse(
#         status="success",
#         file_record_id=file_records.id,
#         storage_key=str(file_records.storage_key)
#     )


@router.post(
    "/{upload_id}/merge",
    response_model=MergeTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED
)
async def merge_chunks(
    upload_id: str = RequestPath(...),
    upload_service: UploadService = Depends()
):
    """
    触发文件合并（非阻塞，返回 202 Accepted）
    """
    task_id = await upload_service.trigger_merge(upload_id=upload_id)
    return MergeTriggerResponse(
        status=UploadStatus.MERGING,
        task_id=task_id,
        upload_id=upload_id
    )