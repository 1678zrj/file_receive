import os

from fastapi import UploadFile, APIRouter, Depends, File, Form, Body, Path as RequestPath, Request, Query, status

from app.db.session import get_session
from app.services.upload_service import UploadService
from app.schemas import upload_schema
from app.schemas.upload_schema import InitUploadResponse, UploadStatusResponse, MergeTriggerResponse
from app.schemas.upload_schema import UploadStatus
from app.rbac.dependencies import get_current_user
from app.models.base import User
from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter()


@router.post("/init", response_model=upload_schema.InitUploadResponse)
async def init_upload(
        upload_info: upload_schema.InitUploadRequest,
        upload_service: UploadService = Depends(),
        db: AsyncSession = Depends(get_session),
        current_user: User = Depends(get_current_user)
):
    upload_session, file_record = await upload_service.init_file_upload(
        current_user.id,
        upload_info.file_name,
        upload_info.file_hash,
        upload_info.file_ext,
        upload_info.mime_type,
        upload_info.total_size,
        upload_info.chunk_size,
        upload_info.total_chunks,
        db
    )
    if file_record is not None:
        return InitUploadResponse(
            instant_upload = True,
            file_record_id = file_record.id,
            upload_id = None,
            uploaded_chunks = []
        )
    if upload_session.status == UploadStatus.COMPLETED and upload_session.file_record_id:
        return InitUploadResponse(
            instant_upload=True,
            file_record_id=upload_session.file_record_id,
            upload_id=upload_session.upload_id,
            uploaded_chunks=list(upload_session.uploaded_chunks)
        )
    return InitUploadResponse(
        instant_upload=False,
        upload_id = upload_session.upload_id,
        uploaded_chunks=list(upload_session.uploaded_chunks)
    )

@router.post("/{upload_id}/chunk")
async def upload_chunk(
        request: Request,
        upload_id: str = RequestPath(...),
        chunk_index: int = Query(...),
        upload_service: UploadService = Depends(),
        current_user: User = Depends(get_current_user)
):

    await upload_service.upload_file_chunk(
        upload_id=upload_id,
        user_id = current_user.id,
        chunk_index=chunk_index,
        chunk_file=request.stream()
    )


@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
        upload_id: str = RequestPath(...),
        upload_service: UploadService = Depends(),
        current_user: User = Depends(get_current_user)
):
    upload_session = await upload_service.get_status(
        upload_id=upload_id,
        user_id=current_user.id
    )
    return UploadStatusResponse(
        upload_id = upload_session.upload_id,
        status = upload_session.status,
        uploaded_chunks = list(upload_session.uploaded_chunks),
        total_chunks = upload_session.total_chunks,
        file_record_id = upload_session.file_record_id,
        error_msg=upload_session.error_msg
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
    upload_service: UploadService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    触发文件合并（非阻塞，返回 202 Accepted）
    """
    merge_status, task_id = await upload_service.trigger_merge(
        upload_id=upload_id,
        user_id=current_user.id
    )
    return MergeTriggerResponse(
        status=merge_status,
        task_id=task_id,
        upload_id=upload_id
    )