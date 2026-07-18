from dataclasses import dataclass, field
from functools import lru_cache

@dataclass
class UploadSession:
    upload_id: str
    file_name: str
    file_hash: str
    file_ext: str
    mime_type: str
    total_size: int
    chunk_size: int
    total_chunks: int
    uploaded_chunks: set[int] = field(default_factory=set)


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, UploadSession] = {}

    def add_session(
            self,
            upload_id: str,
            file_name: str,
            file_hash: str,
            file_ext: str,
            mime_type: str,
            total_size: int,
            chunk_size: int,
            total_chunks: int
    ) -> UploadSession:
        new_session = UploadSession(
            upload_id=upload_id,
            file_name=file_name,
            file_hash=file_hash,
            file_ext=file_ext,
            mime_type=mime_type,
            total_size=total_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks
        )
        self._sessions[upload_id] = new_session
        return new_session

    def get_session(self, upload_id: str) -> UploadSession:
        session = self._sessions.get(upload_id, None)
        if session is None:
            raise ValueError(f"Unknown upload session: {upload_id}")
        return session

    def delete_session(self, upload_id: str):
        session = self._sessions.pop(upload_id, None)
        if session is None:
            raise ValueError(f"Unknown upload session: {upload_id}")

    def add_uploaded_chunk(self, upload_id: str, chunk_index: int):
        session = self._sessions.get(upload_id, None)
        if session is None:
            raise ValueError(f"Unknown upload session: {upload_id}")
        session.uploaded_chunks.add(chunk_index)




@lru_cache()
async def get_session_manager():
    return SessionManager()

