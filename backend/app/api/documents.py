from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.document import Document
from app.models.user import User

router = APIRouter()


@router.get("/{operation_id}")
async def list_documents(
    operation_id: UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    result = await db.execute(select(Document).where(Document.operation_id == operation_id))
    docs = list(result.scalars().all())
    return [
        {"id": str(d.id), "type": d.doc_type.value, "filename": d.filename, "created_at": str(d.created_at)}
        for d in docs
    ]


@router.get("/{operation_id}/{document_id}/download")
async def download_document(
    operation_id: UUID,
    document_id: UUID,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.operation_id == operation_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(doc.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    media_type = "application/pdf" if doc.filename.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return FileResponse(path=str(path), filename=doc.filename, media_type=media_type)
