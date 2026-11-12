import logging
import os
import re
from dataclasses import dataclass

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ChunkVector, Document, DocumentChunk
from app.statuses import DocumentStatus

logger = logging.getLogger(__name__)

_model = None


class VectorWriteError(Exception):
    pass


def _embedding_model():
    global _model
    if _model is None:
        cache = settings.embedding_cache_path
        cache.mkdir(parents=True, exist_ok=True)
        os.environ["FASTEMBED_CACHE_PATH"] = str(cache)
        from fastembed import TextEmbedding

        _model = TextEmbedding(model_name=settings.embedding_model)
    return _model


def passage_text(document: Document, chunk: DocumentChunk) -> str:
    """向量里带上文档名、页码和片段序号，正文里已经有章节路径。"""
    lines = [document.title]
    if chunk.page_number:
        if chunk.page_end and chunk.page_end != chunk.page_number:
            lines.append(f"第{chunk.page_number}-{chunk.page_end}页")
        else:
            lines.append(f"第{chunk.page_number}页")
    lines.append(f"片段{chunk.ordinal + 1}")
    lines.append(chunk.content)
    return "\n".join(lines)


def embed_query(text: str) -> list[float]:
    """问句用和入库片段同一套编码。这个模型不要求另外加检索前缀。"""
    try:
        rows = list(_embedding_model().query_embed(text.strip()))
    except Exception as exc:
        logger.exception("问句向量计算失败")
        raise VectorWriteError("检索失败") from exc
    if not rows:
        raise VectorWriteError("检索失败")
    vector = [float(value) for value in rows[0]]
    if len(vector) != settings.embedding_dim:
        raise VectorWriteError("向量维度和数据库不一致")
    return vector


def embed_texts(texts: list[str]) -> list[list[float]]:
    try:
        rows = list(_embedding_model().embed(texts, batch_size=16))
    except Exception as exc:
        logger.exception("片段向量计算失败")
        raise VectorWriteError("向量写入失败") from exc
    vectors = [[float(value) for value in row] for row in rows]
    if any(len(vector) != settings.embedding_dim for vector in vectors):
        raise VectorWriteError("向量维度和数据库不一致")
    return vectors


def sync_document_vectors(
    db: Session,
    document: Document,
    chunks: list[DocumentChunk],
    *,
    decision: str,
    roles: list[str],
    effective_status: str | None,
) -> None:
    """发布时补齐缺失向量并更新元数据；拒绝或下线时删除该文档的向量。"""
    if decision != DocumentStatus.published:
        db.execute(delete(ChunkVector).where(ChunkVector.document_id == document.id))
        return
    if not chunks:
        raise VectorWriteError("没有片段，不能发布")

    chunk_ids = [chunk.id for chunk in chunks]
    db.execute(
        delete(ChunkVector).where(
            ChunkVector.document_id == document.id,
            ChunkVector.chunk_id.not_in(chunk_ids),
        )
    )
    db.flush()
    existing_ids = set(
        db.scalars(select(ChunkVector.chunk_id).where(ChunkVector.document_id == document.id)).all()
    )
    missing = [chunk for chunk in chunks if chunk.id not in existing_ids]
    if missing:
        vectors = embed_texts([passage_text(document, chunk) for chunk in missing])
        for chunk, vector in zip(missing, vectors, strict=True):
            db.add(
                ChunkVector(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    embedding=vector,
                    status=DocumentStatus.published.value,
                    effective_status=effective_status,
                    access_roles=list(roles),
                )
            )
        db.flush()
        logger.info("文档 %s 写入 %s 条向量", document.id, len(missing))

    db.execute(
        update(ChunkVector)
        .where(ChunkVector.document_id == document.id)
        .values(
            status=DocumentStatus.published.value,
            effective_status=effective_status,
            access_roles=list(roles),
        )
    )


@dataclass
class SearchHit:
    chunk: DocumentChunk
    document: Document
    distance: float
    keyword: bool = False


def _terms(query: str) -> list[str]:
    found: list[str] = []
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9+#.-]{0,24}", query):
        token = match.group(0)
        if len(token) >= 3 or any(char.isdigit() for char in token) or (len(token) >= 2 and token.isupper()):
            found.append(token)
    return found


def search_published(db: Session, query: str, *, role: str, limit: int = 12) -> list[SearchHit]:
    """只查已发布、并且当前角色可见的片段。专名会额外按原文匹配。"""
    vector = embed_query(query)
    distance = ChunkVector.embedding.cosine_distance(vector)
    stmt = (
        select(DocumentChunk, Document, distance.label("distance"))
        .join(ChunkVector, ChunkVector.chunk_id == DocumentChunk.id)
        .join(Document, Document.id == ChunkVector.document_id)
        .where(Document.status == DocumentStatus.published.value)
        .order_by(distance)
        .limit(limit)
    )
    if role != "admin":
        stmt = stmt.where(ChunkVector.access_roles.contains([role]))
    rows = list(db.execute(stmt).all())
    seen = {chunk.id for chunk, _document, _score in rows}
    terms = _terms(query)
    if terms:
        keyword = or_(*(DocumentChunk.content.ilike(f"%{term}%") for term in terms))
        extra = stmt.where(keyword, DocumentChunk.id.not_in(seen) if seen else True).limit(8)
        rows.extend(db.execute(extra).all())
    hits = []
    for chunk, document, score in rows:
        text = chunk.content.lower()
        hits.append(
            SearchHit(
                chunk=chunk,
                document=document,
                distance=float(score),
                keyword=any(term.lower() in text for term in terms),
            )
        )
    hits.sort(key=lambda hit: hit.distance - (0.22 if hit.keyword else 0))
    return hits


def backfill_published(db: Session) -> int:
    documents = list(db.scalars(select(Document).where(Document.status == DocumentStatus.published.value)).all())
    written = 0
    for document in documents:
        chunks = list(
            db.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.ordinal)
            ).all()
        )
        if not chunks:
            continue
        before = set(
            db.scalars(select(ChunkVector.chunk_id).where(ChunkVector.document_id == document.id)).all()
        )
        sync_document_vectors(
            db,
            document,
            chunks,
            decision=DocumentStatus.published.value,
            roles=list(document.access_roles or []),
            effective_status=document.effective_status,
        )
        if len(before) != len(chunks):
            written += 1
    return written
