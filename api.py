import os
import tempfile
import shutil
import subprocess
import uuid
from typing import List, Optional


import psycopg2
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extras import RealDictCursor
from fastapi.responses import HTMLResponse
from data_sources import _load_settings, _compute_embedding

app = FastAPI(title="SPA Backend", version="0.1.0")

# CORS: Panel 프런트에서 호출할 수 있게 기본 허용 (필요 시 도메인 제한)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _pg_conn():
    cfg = _load_settings()["postgres"]
    return psycopg2.connect(**cfg, connect_timeout=5)


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
    return path


def convert_to_pdf(src_path: str) -> str:
    """LibreOffice headless가 있을 때만 변환. 실패하면 원본을 반환."""
    out_dir = tempfile.mkdtemp(prefix="converted_")
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
    except Exception:
        pass
    return src_path  # 변환 실패 시 원본 사용


def extract_text_by_page(pdf_path: str) -> List[str]:
    """페이지별 텍스트 리스트 반환.

    pdfplumber은 네이티브 의존성이 있으므로 이 함수 내에서 lazy-import 처리합니다.
    만약 pdfplumber 또는 그 의존성이 없다면 빈 리스트를 반환합니다.
    """
    texts: List[str] = []
    try:
        import pdfplumber
    except Exception:
        return []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                texts.append(txt.replace("\x00", ""))
    except Exception:
        return []
    return texts


def split_chunks(text: str, max_tokens: int = 500, overlap: int = 50) -> List[str]:
    """
    문장 단위로 나눈 뒤 슬라이딩 윈도우로 청크 생성.
    토크나이저 없이 단어 수 기준으로 근사치.
    """
    import re

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


def process_upload_payload(
    file_payloads: List[tuple],
    title: str,
    system: str,
    category: str,
    owner: str,
    tags: Optional[str],
):
    """
    file_payloads: [("filename", bytes, mime), ...]
    """
    base_dir = _ensure_dir(os.path.join("uploads", uuid.uuid4().hex))
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    inserted = []
    conn = _pg_conn()
    try:
        with conn, conn.cursor() as cur:
            for fname, raw, mime in file_payloads:
                suffix = os.path.splitext(fname)[1].lower()
                save_path = os.path.join(base_dir, fname)
                with open(save_path, "wb") as f:
                    f.write(raw)

                pdf_path = save_path
                if suffix in [".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx"]:
                    pdf_path = convert_to_pdf(save_path)

                cur.execute(
                    """
                    INSERT INTO documents (title, category, system, owner, tags, source_type, original_path, converted_pdf)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (title, category, system, owner, tag_list, suffix.lstrip("."), save_path, pdf_path),
                )
                doc_id = cur.fetchone()[0]

                texts_per_page = extract_text_by_page(pdf_path) if pdf_path.lower().endswith(".pdf") else []

                inserted_chunk_count = 0
                for page_idx, page_text in enumerate(texts_per_page, start=1):
                    chunks = split_chunks(page_text)
                    embeddings = []
                    for c in chunks:
                        emb = _compute_embedding(c)
                        if emb is None:
                            raise ValueError("임베딩 생성 실패: OPENAI_API_KEY를 확인하세요.")
                        embeddings.append(emb)
                    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                        cur.execute(
                            """
                            INSERT INTO doc_chunks (document_id, chunk_index, content, page_num, source_path, highlight_anchor, embedding)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (doc_id, idx, chunk, page_idx, pdf_path, None, emb),
                        )
                        inserted_chunk_count += 1

                # 페이지가 없거나 추출 실패 시 전체 텍스트를 한 번 더 시도
                if not texts_per_page:
                    all_text = ""
                    try:
                        all_text = extract_text_by_page(pdf_path)
                        all_text = "\n".join(all_text)
                    except Exception:
                        all_text = ""
                    all_chunks = split_chunks(all_text)
                    embeddings = []
                    for c in all_chunks:
                        emb = _compute_embedding(c)
                        if emb is None:
                            raise ValueError("임베딩 생성 실패: OPENAI_API_KEY를 확인하세요.")
                        embeddings.append(emb)
                    for idx, (chunk, emb) in enumerate(zip(all_chunks, embeddings)):
                        cur.execute(
                            """
                            INSERT INTO doc_chunks (document_id, chunk_index, content, page_num, source_path, highlight_anchor, embedding)
                            VALUES (%s,%s,%s,%s,%s,%s,%s)
                            """,
                            (doc_id, idx, chunk, None, pdf_path, None, emb),
                        )
                        inserted_chunk_count += 1

                inserted.append({"document_id": doc_id, "file": fname, "chunks": inserted_chunk_count})
        return {"status": "ok", "inserted": inserted}
    finally:
        conn.close()


@app.get("/health")
def health():
    """간단한 헬스 체크."""
    return {"status": "ok"}


@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    title: str = Form(...),
    system: str = Form(...),
    category: str = Form(...),
    owner: str = Form(...),
    tags: Optional[str] = Form(None),
):
    """파일 업로드 → 변환/추출/임베딩/적재."""
    payloads = []
    for uf in files:
        raw = await uf.read()
        payloads.append((uf.filename or "file.bin", raw, uf.content_type))
    return process_upload_payload(payloads, title, system, category, owner, tags)


@app.post("/chat")
async def chat(query: str):
    """
    간단한 RAG:
    - 쿼리 임베딩 → pgvector Top-K 검색 → 스니펫/링크 반환
    - LLM 본문 생성은 생략하고 검색 결과를 요약한 문자열만 반환
    """
    embedding = _compute_embedding(query)
    if not embedding:
        return {"answer": "임베딩을 생성할 수 없습니다. OPENAI_API_KEY를 설정하세요.", "sources": []}

    try:
        with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.title,
                       d.converted_pdf,
                       dc.page_num,
                       dc.content,
                       1 - (dc.embedding <=> %s::vector) AS score
                FROM doc_chunks dc
                JOIN documents d ON d.id = dc.document_id
                ORDER BY dc.embedding <=> %s::vector
                LIMIT 5
                """,
                (embedding, embedding),
            )
            rows = cur.fetchall()
    except Exception as e:
        return {"answer": f"검색 중 오류: {e}", "sources": []}

    sources = []
    snippets = []
    for r in rows:
        src = {
            "title": r.get("title"),
            "link": r.get("converted_pdf") or "",
            "page": r.get("page_num"),
            "score": float(r.get("score", 0)),
            "snippet": (r.get("content") or "")[:300],
        }
        sources.append(src)
        snippets.append(f"- {src['title']} (score={src['score']:.3f})")

    answer_text = "검색 결과 상위 문서:\n" + "\n".join(snippets) if snippets else "검색 결과가 없습니다."
    return {"answer": answer_text, "sources": sources}


@app.get("/uploads")
async def list_uploads(tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID")):
    """Simple tenant-scoped uploads list placeholder for tests.
    Returns 401 when X-Tenant-ID header is missing (test expects this behavior).
    """
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Tenant ID required")
    # Minimal placeholder: return empty list (real implementation will query DB)
    return []


@app.get("/pdf_viewer", response_class=HTMLResponse)
async def get_pdf_viewer(file: str, page: int = 1, query: str = ""):
    """PDF.js 뷰어를 iframe에 렌더링하고, 쿼리 텍스트를 하이라이트합니다."""
    pdf_url = f"/uploads/{file}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PDF Viewer</title>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; background-color: #525659; display: flex; justify-content: center; align-items: flex-start; }}
            #pdf-container {{
                margin-top: 20px;
                position: relative;
                box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            }}
            #pdf-canvas, #highlight-canvas {{
                position: absolute;
                top: 0;
                left: 0;
                direction: ltr;
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
        <script>
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
        </script>
    </head>
    <body>
        <div id="pdf-container">
            <canvas id="pdf-canvas"></canvas>
            <canvas id="highlight-canvas"></canvas>
        </div>

        <script>
            const url = '{pdf_url}';
            const pageNum = parseInt('{page}');
            const query = `{query}`.trim();
            
            const pdfCanvas = document.getElementById('pdf-canvas');
            const highlightCanvas = document.getElementById('highlight-canvas');
            const container = document.getElementById('pdf-container');

            async function renderPdf() {{
                try {{
                    const pdf = await pdfjsLib.getDocument(url).promise;
                    const page = await pdf.getPage(pageNum);
                    
                    const scale = 1.5;
                    const viewport = page.getViewport({{ scale: scale }});

                    container.style.width = viewport.width + 'px';
                    container.style.height = viewport.height + 'px';
                    
                    pdfCanvas.width = highlightCanvas.width = viewport.width;
                    pdfCanvas.height = highlightCanvas.height = viewport.height;
                    
                    const pdfContext = pdfCanvas.getContext('2d');
                    await page.render({{ canvasContext: pdfContext, viewport: viewport }}).promise;
                    
                    if (query) {{
                        await highlightText(page, viewport, query);
                    }}

                }} catch (error) {{
                    console.error('Error rendering PDF:', error);
                    container.innerText = 'PDF를 로드할 수 없습니다. 파일 경로를 확인하세요.';
                }}
            }}

            async function highlightText(page, viewport, searchText) {{
                const textContent = await page.getTextContent();
                const highlightContext = highlightCanvas.getContext('2d');
                highlightContext.fillStyle = 'rgba(255, 255, 0, 0.4)';

                const normalize = (str) => str.replace(/\\s+/g, '').toLowerCase();
                const searchWords = normalize(searchText).split(/\\s+/).filter(Boolean);

                if (searchWords.length === 0) return;

                const textItems = textContent.items.map(item => ({{
                    text: normalize(item.str),
                    transform: item.transform,
                    width: item.width,
                    height: item.height,
                    originalText: item.str
                }}));

                let matchStartIndex = -1;
                let currentMatch = [];
                
                for (let i = 0; i < textItems.length; i++) {{
                    const itemText = textItems[i].text;
                    if (!itemText) continue;

                    if (matchStartIndex === -1) {{
                        if (searchWords[0].startsWith(itemText)) {{
                            matchStartIndex = i;
                            currentMatch.push(textItems[i]);
                        }}
                    }} else {{
                        currentMatch.push(textItems[i]);
                    }}

                    const combinedText = currentMatch.map(it => it.text).join('');
                    
                    if (searchWords.join('').startsWith(combinedText)) {{
                        if (searchWords.join('') === combinedText) {{
                            drawHighlights(currentMatch, viewport, highlightContext);
                            matchStartIndex = -1;
                            currentMatch = [];
                        }}
                    }} else {{
                        matchStartIndex = -1;
                        currentMatch = [];
                        // Retry current item in case it starts a new match
                        i--; 
                    }}
                }}
            }}

            function drawHighlights(items, viewport, context) {{
                items.forEach(item => {{
                    const [scaleX, , , scaleY, offsetX, offsetY] = item.transform;
                    const x = offsetX;
                    const y = viewport.height - offsetY - (item.height * scaleY);

                    context.fillRect(x, y, item.width * scaleX, item.height * scaleY);
                }});
            }}

            renderPdf();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# --- Panel에서 직접 호출할 수 있는 헬퍼 ---
def upload_via_python(file_payloads: List[tuple], title: str, system: str, category: str, owner: str, tags: Optional[str]):
    """Panel 콜백에서 HTTP 없이 직접 호출하기 위한 헬퍼."""
    return process_upload_payload(file_payloads, title, system, category, owner, tags)


def chat_search(query: str):
    """Panel 콜백에서 HTTP 없이 직접 호출하기 위한 헬퍼."""
    embedding = _compute_embedding(query)
    if not embedding:
        return {"answer": "임베딩을 생성할 수 없습니다. OPENAI_API_KEY를 설정하세요.", "sources": []}
    try:
        with _pg_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT d.title,
                       d.converted_pdf,
                       dc.page_num,
                       dc.content,
                       1 - (dc.embedding <=> %s::vector) AS score
                FROM doc_chunks dc
                JOIN documents d ON d.id = dc.document_id
                ORDER BY dc.embedding <=> %s::vector
                LIMIT 5
                """,
                (embedding, embedding),
            )
            rows = cur.fetchall()
    except Exception as e:
        return {"answer": f"검색 중 오류: {e}", "sources": []}
    sources = []
    snippets = []
    for r in rows:
        src = {
            "title": r.get("title"),
            "link": r.get("converted_pdf") or "",
            "page": r.get("page_num"),
            "score": float(r.get("score", 0)),
            "snippet": (r.get("content") or "")[:300],
        }
        sources.append(src)
        snippets.append(f"- {src['title']} (score={src['score']:.3f})")
    answer_text = "검색 결과 상위 문서:\n" + "\n".join(snippets) if snippets else "검색 결과가 없습니다."
    return {"answer": answer_text, "sources": sources}
