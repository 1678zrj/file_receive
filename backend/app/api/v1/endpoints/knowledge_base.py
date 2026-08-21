from fastapi import APIRouter
from app.schemas.knowledge_base_schema import CourseFileIndexRequest, CourseFileIndexResponse
from app.services.rag_index_service import RAGIndexService
from fastapi import Depends
from app.rbac.permissions import Permission
from app.rbac.dependencies import require_perm
from app.models.base import User

router = APIRouter()


@router.post("/course", response_model=CourseFileIndexResponse)
async def course_file_index(
        course_file_index: CourseFileIndexRequest,
        rag_index_service: RAGIndexService = Depends(),
        teacher: User = Depends(require_perm(Permission.COURSE_KB_INDEX))
):
    new_kb_doc = await rag_index_service.index_course_file(
        file_record_id=course_file_index.file_record_id,
        course_id=course_file_index.course_id,
        teacher_id=teacher.id,
        splitter_type=course_file_index.splitter_type,
        chunk_size=course_file_index.chunk_size,
        scope=course_file_index.scope,
    )

    return new_kb_doc
