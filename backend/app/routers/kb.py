import io
import math
import re
from collections import Counter

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from .. import llm
from ..config import settings
from ..db import get_db
from ..models import KbChunk, KbDocument, KbQuery
from ..schemas import (
    KbAskRequest,
    KbAskResponse,
    KbChunkOut,
    KbChunkUsed,
    KbDocumentCreate,
    KbDocumentDetailOut,
    KbDocumentOut,
    KbRetrieveRequest,
    KbRetrieveResponse,
    KbRetrieveResult,
)
from ..security import CurrentUser, get_current_user

router = APIRouter(prefix="/kb", tags=["knowledge-base"])

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
LOCAL_EMBEDDING_MODEL = "local-lexical-v1"
LEXICAL_THRESHOLD = 0.15
OPENAI_THRESHOLD = 0.35
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "at", "by", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after", "above",
    "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
    "further", "once", "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "can", "will", "just", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "it", "its", "this", "that",
    "these", "those", "i", "you", "he", "she", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "our", "their", "what", "which", "who", "whom", "as",
}


# ---------- Text extraction ----------
def extract_text(name: str, raw: bytes) -> tuple[str, str]:
    """Return (doc_type, text). Raises ValueError with the real failure reason."""
    lower = name.lower()
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError(f"PDF support is unavailable (pypdf not installed): {exc}")
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = [(page.extract_text() or "") for page in reader.pages]
        except Exception as exc:
            raise ValueError(f"Could not read this PDF: {exc}")
        return "PDF", "\n".join(pages)
    if lower.endswith(".docx"):
        try:
            import docx
        except ImportError as exc:
            raise ValueError(f"DOCX support is unavailable (python-docx not installed): {exc}")
        try:
            document = docx.Document(io.BytesIO(raw))
            paragraphs = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    for cell in row.cells:
                        paragraphs.append(cell.text)
        except Exception as exc:
            raise ValueError(f"Could not read this DOCX: {exc}")
        return "DOCX", "\n".join(paragraphs)
    if lower.endswith(".csv"):
        return "CSV", raw.decode("utf-8", errors="replace")
    # Default: treat as plain text.
    return "TXT", raw.decode("utf-8", errors="replace")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + size, length)
        if end < length:
            window = text[start:end]
            cut = max(window.rfind(". "), window.rfind(".\n"), window.rfind("! "), window.rfind("? "))
            if cut > size // 2:
                end = start + cut + 1
            else:
                space = window.rfind(" ")
                if space > size // 2:
                    end = start + space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        next_start = max(end - overlap, start + 1)
        space = text.find(" ", next_start)
        if space != -1 and space < end:
            next_start = space + 1
        start = next_start
    return chunks


# ---------- Embeddings ----------
def _tokenize(text: str) -> list[str]:
    tokens = []
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in STOPWORDS or len(word) < 2:
            continue
        for suffix in ("ing", "ed"):
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                word = word[: -len(suffix)]
                break
        else:
            if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
                word = word[:-1]
        tokens.append(word)
    return tokens


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


def _lexical_vectors(chunk_texts: list[str]) -> tuple[list[str], list[list[float]]]:
    tokenized = [_tokenize(t) for t in chunk_texts]
    vocab = sorted({token for tokens in tokenized for token in tokens})
    index = {token: i for i, token in enumerate(vocab)}
    vectors = []
    for tokens in tokenized:
        counts = Counter(tokens)
        vector = [0.0] * len(vocab)
        for token, count in counts.items():
            vector[index[token]] = float(count)
        vectors.append(_normalize(vector))
    return vocab, vectors


def _lexical_query_vector(question: str, vocab: list[str]) -> list[float]:
    index = {token: i for i, token in enumerate(vocab)}
    counts = Counter(_tokenize(question))
    vector = [0.0] * len(vocab)
    for token, count in counts.items():
        if token in index:
            vector[index[token]] = float(count)
    return _normalize(vector)


def _openai_embeddings(texts: list[str]) -> list[list[float]] | None:
    """Embed with OpenAI; return None on ANY failure so callers can fall back.

    Only attempted when LLM_PROVIDER is "openai" AND an OpenAI key is set;
    in all other cases (including the default Groq configuration) callers go
    straight to the labeled local lexical vectors and the OpenAI
    embeddings endpoint is never called.
    """
    if (settings.LLM_PROVIDER or "groq").strip().lower() != "openai" or not settings.OPENAI_API_KEY or not texts:
        return None
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                OPENAI_EMBEDDINGS_URL,
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={"model": OPENAI_EMBEDDING_MODEL, "input": texts},
            )
        if resp.status_code != 200:
            return None
        data = resp.json().get("data") or []
        if len(data) != len(texts):
            return None
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in ordered]
    except Exception:
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_chunks(chunk_texts: list[str]) -> tuple[str, list[str], list[list[float]]]:
    """Return (embedding_model, vocab, vectors) for a document's chunks."""
    vectors = _openai_embeddings(chunk_texts)
    if vectors is not None:
        return OPENAI_EMBEDDING_MODEL, [], vectors
    vocab, lexical = _lexical_vectors(chunk_texts)
    return LOCAL_EMBEDDING_MODEL, vocab, lexical


def _process_document(db: Session, document: KbDocument, raw_text: str):
    """Clean, chunk and embed a document's text; set its final status."""
    cleaned = clean_text(raw_text or "")
    document.extracted_text = cleaned
    db.query(KbChunk).filter(KbChunk.document_id == document.id).delete(synchronize_session=False)
    db.flush()
    if not cleaned:
        document.status = "Failed"
        document.error = "No extractable text was found in this document."
        document.chunk_count = 0
        document.embedding_model = ""
        document.vocab = []
        db.commit()
        return
    texts = chunk_text(cleaned)
    model, vocab, vectors = _embed_chunks(texts)
    document.embedding_model = model
    document.vocab = vocab
    for index, (text, vector) in enumerate(zip(texts, vectors)):
        db.add(
            KbChunk(
                org_id=document.org_id,
                document_id=document.id,
                chunk_index=index,
                text=text,
                embedding=vector,
                embedding_model=model,
            )
        )
    document.chunk_count = len(texts)
    document.status = "Ready"
    document.error = ""
    db.commit()


def _get_document_or_404(db: Session, org_id: str, document_id: str) -> KbDocument:
    document = db.get(KbDocument, document_id)
    if document is None or document.org_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


# ---------- Retrieval ----------
def retrieve(db: Session, org_id: str, question: str, top_k: int) -> list[dict]:
    """Cosine search over the org's chunks, embedding the query with the same
    model as the chunks being searched."""
    chunks = db.query(KbChunk).filter(KbChunk.org_id == org_id).all()
    if not chunks:
        return []
    documents = {
        doc.id: doc
        for doc in db.query(KbDocument).filter(KbDocument.org_id == org_id).all()
    }
    scored: list[dict] = []

    openai_chunks = [c for c in chunks if c.embedding_model == OPENAI_EMBEDDING_MODEL]
    if openai_chunks:
        query_vectors = _openai_embeddings([question])
        if query_vectors:
            query_vector = query_vectors[0]
            for chunk in openai_chunks:
                score = _cosine(query_vector, chunk.embedding or [])
                if score >= OPENAI_THRESHOLD:
                    scored.append(_result(chunk, documents, score))

    lexical_chunks = [c for c in chunks if c.embedding_model != OPENAI_EMBEDDING_MODEL]
    by_document: dict[str, list[KbChunk]] = {}
    for chunk in lexical_chunks:
        by_document.setdefault(chunk.document_id, []).append(chunk)
    for document_id, doc_chunks in by_document.items():
        document = documents.get(document_id)
        vocab = (document.vocab if document else None) or []
        if not vocab:
            continue
        query_vector = _lexical_query_vector(question, vocab)
        if not any(query_vector):
            continue
        for chunk in doc_chunks:
            score = _cosine(query_vector, chunk.embedding or [])
            if score >= LEXICAL_THRESHOLD:
                scored.append(_result(chunk, documents, score))

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, top_k)]


def _result(chunk: KbChunk, documents: dict, score: float) -> dict:
    document = documents.get(chunk.document_id)
    return {
        "document_id": chunk.document_id,
        "document_name": document.name if document else "",
        "chunk_index": chunk.chunk_index,
        "score": round(float(score), 4),
        "text": chunk.text,
    }


# ---------- Endpoints ----------
@router.post("/documents", response_model=KbDocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = KbDocumentCreate.model_validate(await request.json())
        except Exception:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "JSON body must be {name, text}")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "A document name is required")
        document = KbDocument(
            org_id=current.org_id,
            name=name,
            doc_type="TXT",
            size_bytes=len(payload.text.encode("utf-8")),
            status="Processing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        _process_document(db, document, payload.text)
        db.refresh(document)
        return document

    form = await request.form()
    file = form.get("file")
    if not isinstance(file, UploadFile):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Upload a file in the 'file' field, or send JSON {name, text}",
        )
    raw = await file.read()
    name = file.filename or "Untitled document"
    document = KbDocument(
        org_id=current.org_id,
        name=name,
        doc_type="",
        size_bytes=len(raw),
        status="Processing",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    try:
        doc_type, text = extract_text(name, raw)
        document.doc_type = doc_type
        db.commit()
    except ValueError as exc:
        document.status = "Failed"
        document.error = str(exc)
        db.commit()
        db.refresh(document)
        return document
    _process_document(db, document, text)
    db.refresh(document)
    return document


@router.get("/documents", response_model=list[KbDocumentOut])
def list_documents(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(KbDocument)
        .filter(KbDocument.org_id == current.org_id)
        .order_by(KbDocument.created_at.desc())
        .all()
    )


@router.get("/documents/{document_id}", response_model=KbDocumentDetailOut)
def get_document(document_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document_or_404(db, current.org_id, document_id)
    chunks = (
        db.query(KbChunk)
        .filter(KbChunk.document_id == document.id)
        .order_by(KbChunk.chunk_index.asc())
        .all()
    )
    detail = KbDocumentDetailOut.model_validate(document)
    detail.chunks = [KbChunkOut.model_validate(c) for c in chunks]
    return detail


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document_or_404(db, current.org_id, document_id)
    db.query(KbChunk).filter(KbChunk.document_id == document.id).delete(synchronize_session=False)
    db.delete(document)
    db.commit()
    return None


@router.post("/documents/{document_id}/reindex", response_model=KbDocumentOut)
def reindex_document(document_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    document = _get_document_or_404(db, current.org_id, document_id)
    if not document.extracted_text:
        document.status = "Failed"
        document.error = "No extracted text is stored for this document, so it cannot be reindexed."
        db.commit()
        db.refresh(document)
        return document
    document.status = "Processing"
    db.commit()
    _process_document(db, document, document.extracted_text)
    db.refresh(document)
    return document


@router.post("/retrieve", response_model=KbRetrieveResponse)
def retrieve_chunks(body: KbRetrieveRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    results = retrieve(db, current.org_id, body.question, body.top_k)
    return KbRetrieveResponse(found=bool(results), results=[KbRetrieveResult(**r) for r in results])


@router.post("/ask", response_model=KbAskResponse)
def ask_kb(body: KbAskRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    results = retrieve(db, current.org_id, body.question, 4)
    if not results:
        answer = (
            "That information isn't in the uploaded documents, so I can't answer it from the knowledge base. "
            "Try uploading a document that covers it, or rephrase the question."
        )
        db.add(KbQuery(org_id=current.org_id, question=body.question, found=False, top_score=None, chunks_used=[], answer=answer))
        db.commit()
        return KbAskResponse(found=False, answer=answer, chunks_used=[])

    context = "\n\n".join(f"[{r['document_name']}] {r['text']}" for r in results)
    # Raises HTTPException as-is (503 not-connected or provider error verbatim).
    answer = llm.chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Answer the question using ONLY the document excerpts provided. "
                    "Do not use outside knowledge. Cite the source document inline as [Document Name] "
                    "for each fact you use. If the excerpts do not contain the answer, say so plainly."
                ),
            },
            {"role": "user", "content": f"Document excerpts:\n{context}\n\nQuestion: {body.question}"},
        ]
    ).strip()
    if not answer:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LLM returned an empty answer")

    chunks_used = [
        KbChunkUsed(document_id=r["document_id"], document_name=r["document_name"], chunk_index=r["chunk_index"], score=r["score"])
        for r in results
    ]
    db.add(
        KbQuery(
            org_id=current.org_id,
            question=body.question,
            found=True,
            top_score=results[0]["score"],
            chunks_used=[c.model_dump() for c in chunks_used],
            answer=answer,
        )
    )
    db.commit()
    return KbAskResponse(found=True, answer=answer, chunks_used=chunks_used)
