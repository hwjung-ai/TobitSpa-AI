import os
import tempfile
import shutil
import subprocess
import uuid
import re
import json
import logging
import threading
from typing import List, Optional

from db.connections import get_pg_conn
from db.embedding import compute_embedding
from config.settings import load_settings

from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Simple background executor for async processing
_executor = ThreadPoolExecutor(max_workers=4)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
    return path


def convert_to_pdf(src_path: str) -> str:
    """LibreOffice headless가 있을 때만 변환. 실패하면 원본 파일 반환."""
    out_dir = tempfile.mkdtemp(prefix=" converted_")
    try:
        subprocess.check_call(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", out_dir, src_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base = os.path.splitext(os.path.basename(src_path))[0] + ".pdf"
        pdf_path = os.path.join(out_dir, base)
        if os.path.exists(pdf_path):
            return pdf_path
    except Exception as e:
        logger.warning(f"PDF 변환 실패: {e}. 원본 파일 사용.")
    return src_path  # 변환 실패 시 원본 사용


def extract_text_by_page(pdf_path: str) -> List[str]:
    """페이지별 텍스트 리스트 반환."""
    import pdfplumber  # Moved import locally to minimize top-level dependencies
    texts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                texts.append(txt.replace("\x00", ""))
    except Exception as e:
        logger.error(f"PDF 텍스트 추출 실패: {e}")
        return []
    return texts


def split_chunks(text: str, max_tokens: int = 500, overlap: int = 50, mode: str = 'page') -> List[str]:
    """
    문장 단위로 나눈 뒤 슬라이딩 윈도우로 청크 생성.
    토크나이저 없이 단어 수 기준으로 근사치.
    mode: 'page'|'paragraph'|'sentence'
    """
    if mode == 'paragraph':
        paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = []
        for p in paras:
            words = p.split()
            if len(words) > max_tokens:
                # break into sub-chunks
                for i in range(0, len(words), max_tokens):
                    chunks.append(" ".join(words[i:i+max_tokens]))
            else:
                chunks.append(p)
        return chunks
    # default and 'sentence' mode behaves like page for now
    sentences = re.split(r"(?<=[.!?。？！\n])\s+", text.strip())
    sentences = [s for s in sentences if s]
    chunks = []
    buf = []
    buf_len = 0
    for sent in sentences:
        words = sent.split()
        if buf_len + len(words) > max_tokens and buf:
            chunks.append(" ".join(buf))
            # overlap 적용
            if overlap > 0:
                buf = buf[-overlap:]
                buf_len = sum(len(b.split()) for b in buf)
            else:
                buf = []
                buf_len = 0
        buf.append(sent)
        buf_len += len(words)
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def _create_upload(cur, title: str, owner: str, tenant_id: Optional[str], total_files: int, status: str = 'processing'):
    """Create an upload record and return its id."""
    cur.execute(
        """
        INSERT INTO uploads (title, owner, tenant_id, total_files, status)
        VALUES (%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (title, owner, tenant_id, total_files, status),
    )
    return cur.fetchone()[0]


def _process_doc_async(doc_id: int, pdf_path: str, tenant_id: Optional[str], upload_id: Optional[int], chunk_mode: str = 'page'):
    """Background processing for a single document: extract text, chunk, embed, and store chunks."""
    try:
        conn = get_pg_conn()
        with conn, conn.cursor() as cur:
            # Determine mode and process
            texts_per_page = extract_text_by_page(pdf_path) if pdf_path.lower().endswith(".pdf") else []
            inserted_chunk_count = 0
            if texts_per_page:
                for page_idx, page_text in enumerate(texts_per_page, start=1):
                    chunks = split_chunks(page_text, mode=chunk_mode)
                    embeddings = []
                    for c in chunks:
                        emb = compute_embedding(c)
                        if emb is None:
                            logger.warning("임베딩 생성 실패: OPENAI_API_KEY를 확인하세요.")
                            continue
                        embeddings.append(emb)
                    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                        cur.execute(
                            """
                            INSERT INTO doc_chunks (document_id, chunk_index, content, page_num, source_path, highlight_anchor, embedding, tenant_id, chunk_type)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (doc_id, idx, chunk, page_idx, pdf_path, None, emb, tenant_id, chunk_mode),
                        )
                        inserted_chunk_count += 1
            # Fallback for no-page extraction
            if not texts_per_page:
                all_text = ""
                try:
                    all_text = "\\n".join(extract_text_by_page(pdf_path))
                except Exception:
                    all_text = ""
                all_chunks = split_chunks(all_text, mode=chunk_mode)
                embeddings = []
                for c in all_chunks:
                    emb = compute_embedding(c)
                    if emb is None:
                        logger.warning("임베딩 생성 실패: OPENAI_API_KEY를 확인하세요.")
                        continue
                    embeddings.append(emb)
                for idx, (chunk, emb) in enumerate(zip(all_chunks, embeddings)):
                    cur.execute(
                        """
                        INSERT INTO doc_chunks (document_id, chunk_index, content, page_num, source_path, highlight_anchor, embedding, tenant_id, chunk_type)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (doc_id, idx, chunk, None, pdf_path, None, emb, tenant_id, chunk_mode),
                    )
                    inserted_chunk_count += 1
            logger.info(f"Doc {doc_id}: inserted {inserted_chunk_count} chunks (async).")
        conn.close()
    except Exception as e:
        logger.error(f"Async doc processing failed for doc_id={doc_id}: {e}")


def process_upload_payload(
    file_payloads: List[tuple],
    title: str,
    system: str,
    category: str,
    owner: str,
    tags: Optional[str],
    tenant_id: Optional[str],
    chunk_mode: str = 'page',
):
    """
    file_payloads: [("filename", bytes, mime), ...]
    """
    base_dir = _ensure_dir(os.path.join("uploads", uuid.uuid4().hex))
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    inserted = []
    upload_id = None
    # Use the global pg connection
    conn = get_pg_conn()
    try:
        with conn, conn.cursor() as cur:
            # Set tenant context for this session if provided
            if tenant_id is not None:
                try:
                    cur.execute("SELECT set_config('tobitspa.tenant_id', %s, false);", (tenant_id,))
                except Exception as e:
                    logger.warning(f"Failed to set tenant context: {e}")
            # Create an upload record if there are files to process
            if file_payloads:
                upload_id = _create_upload(cur, title, owner, tenant_id, len(file_payloads), 'processing')
            for fname, raw, mime in file_payloads:
                suffix = os.path.splitext(fname)[1].lower()
                save_path = os.path.join(base_dir, fname)
                with open(save_path, "wb") as f:
                    f.write(raw)

                pdf_path = save_path
                if suffix in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]:
                    tmp_pdf = convert_to_pdf(save_path)
                    # Ensure converted PDF is stored under uploads for static serving
                    if tmp_pdf and tmp_pdf.lower().endswith(".pdf") and os.path.exists(tmp_pdf):
                        target_pdf = os.path.join(base_dir, os.path.basename(tmp_pdf))
                        try:
                            if tmp_pdf != target_pdf:
                                shutil.copy2(tmp_pdf, target_pdf)
                            pdf_path = target_pdf
                        except Exception as e:
                            logger.warning(f"Failed to copy converted PDF to uploads: {e}. Using temporary path.")
                            pdf_path = tmp_pdf
                    else:
                        pdf_path = save_path

                cur.execute(
                    """
                    INSERT INTO documents (title, category, system, owner, tags, source_type, original_path, converted_pdf, tenant_id, upload_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (title, category, system, owner, tag_list, suffix.lstrip("."), save_path, pdf_path, tenant_id, upload_id),
                )
                doc_id = cur.fetchone()[0]

                # Async processing: enqueue doc for chunk creation
                _executor.submit(_process_doc_async, doc_id, pdf_path, tenant_id, upload_id, chunk_mode)

                inserted.append({"document_id": doc_id, "file": fname, "chunks": 0})
        return {"status": "ok", "inserted": inserted, "upload_id": upload_id}
    finally:
        conn.close()
