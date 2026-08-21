from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.rag import KnowledgeDocument


class KnowledgeBaseCrud:

    async def create_kb_document(self, db: AsyncSession, kb_doc_data_dict: dict) -> KnowledgeDocument:
        new_kb_doc = KnowledgeDocument(**kb_doc_data_dict)
        db.add(new_kb_doc)
        await db.flush()
        return new_kb_doc


knowledge_base_crud = KnowledgeBaseCrud()