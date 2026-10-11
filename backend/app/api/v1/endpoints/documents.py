import asyncio

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.api.deps import get_document_store, limit_pages
from app.services.document_store import DocumentStore
from app.services.pdf_pages import render_page_png

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get(
    "/{document_id}/pages/{page}.png",
    summary="Render one page of an uploaded document as a PNG (page numbers start at 1)",
    dependencies=[Depends(limit_pages)],
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def get_page(
    document_id: str,
    page: int = Path(ge=1),
    store: DocumentStore = Depends(get_document_store),
) -> Response:
    doc = store.get(document_id)
    if doc is None or page > doc.pages:
        # The same answer for "never existed", "expired" and "no such page": nothing to learn from the status.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document or page not found, or the document has expired.")
    png = await asyncio.to_thread(render_page_png, doc.data, page - 1)
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an uploaded document now")
async def delete_document(document_id: str, store: DocumentStore = Depends(get_document_store)) -> Response:
    store.delete(document_id)  # idempotent: deleting something already gone is fine
    return Response(status_code=status.HTTP_204_NO_CONTENT)
