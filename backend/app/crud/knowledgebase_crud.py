from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.rag import KnowledgeDoc, DocumentStatus, KnowledgeDocChunk
from sqlmodel import select, update, delete


class KnowledgeBaseCrud:

    async def create_kb_doc(self, db: AsyncSession, kb_doc_data_dict: dict) -> KnowledgeDoc:
        new_kb_doc = KnowledgeDoc(**kb_doc_data_dict)
        db.add(new_kb_doc)
        await db.flush()
        return new_kb_doc

    async def create_kb_doc_chunks(self, db: AsyncSession, kb_doc_chunk_data_list: list[dict]) -> list[KnowledgeDocChunk]:
        knowledge_doc_chunks = [
            KnowledgeDocChunk(**kb_doc_chunk_data)
            for kb_doc_chunk_data in kb_doc_chunk_data_list
        ]
        db.add_all(knowledge_doc_chunks)
        await db.flush()
        return knowledge_doc_chunks

    async def get_kb_doc_by_id(self, db: AsyncSession, id: int) -> KnowledgeDoc:
        stat = select(KnowledgeDoc).where(
            KnowledgeDoc.id == id
        )
        result = await db.exec(stat)
        return result.first()


    async def get_kb_doc(self, db: AsyncSession,file_record_id: int, scope: str, scope_id: str) -> KnowledgeDoc:
        stat = select(KnowledgeDoc).where(
            KnowledgeDoc.file_record_id == file_record_id,
            KnowledgeDoc.scope == scope,
            KnowledgeDoc.scope_id == scope_id
        )
        res = await db.exec(stat)
        return res.first()

    async def update_kb_doc_parsing_status(self, db: AsyncSession, id: int) -> int:
        stat = update(KnowledgeDoc).where(
            KnowledgeDoc.id == id,
            KnowledgeDoc.status == DocumentStatus.FAILED
        ).values(
            status=DocumentStatus.PARSING,
            error_msg = None,
            chunk_count = 0
        )
        result = await db.exec(stat)
        await db.commit()
        return result.rowcount

    async def update_kb_doc_failed_status(self, db: AsyncSession, id: int, error_msg: str):
        stmt = (
            update(KnowledgeDoc)
            .where(KnowledgeDoc.id == id)
            .values(
                status=DocumentStatus.FAILED,
                error_msg=error_msg
            )
        )
        await db.execute(stmt)


    async def delete_chunk_by_doc_id(self, db: AsyncSession, knowledge_doc_id: int):
        stat = delete(KnowledgeDocChunk).where(
            KnowledgeDocChunk.knowledge_doc_id == knowledge_doc_id
        )
        await db.exec(stat)




knowledge_base_crud = KnowledgeBaseCrud()