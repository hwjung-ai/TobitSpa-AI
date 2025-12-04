TODO PROGRESS
- [x] Phase 1: Data model, migrations, and platform readiness
- [x] Phase 2: Upload history endpoints
- [ ] Phase 3: Asynchronous upload processing
- [ ] Phase 4: Chunk granularity and metadata
- [ ] Phase 5: Retrieval improvements
- [ ] Phase 6: Multi-tenancy and security hardening
- [ ] Phase 7: UI improvements (Upload tab)
- [ ] Phase 8: Testing and QA
- [ ] Phase 9: Deployment and ops

MVP Plan: Document Upload & Vectorization Pipeline

- Objective
  - Implement an end-to-end MVP for uploading documents, parsing, chunking, vectorizing, and storing results with a scalable path for async processing, upload history, and multi-tenant support.

- Scope
  - Current focus: ensure upload flow stores documents and chunks with proper linkage, and supports basic UI and history tracking. Future work includes deeper chunk granularity, extended search, and admin analytics.

- MVP Phases
  1) Async Upload & Upload History
     - Add an uploads table (id, title, owner, tenant_id, total_files, status, created_at).
     - Link documents to uploads via upload_id (existing migration 20251204_alter_documents_upload_fk_cascade.sql).
     - Extend document_processing.process_upload_payload to create an upload record when files are present and update status as processing/done.
     - Introduce a simple background worker (thread pool) to process files asynchronously and update status in DB.
     - UI/endpoint: Upload tab stores metadata and displays progress/status from uploads table.
  2) Chunk Granularity (page/paragraph/sentence)
     - Extend chunking logic to support granularity modes: page (default), paragraph, sentence.
     - Record chunk_type in doc_chunks for downstream retrieval and UI display decisions.
     - Ensure chunking respects memory/time constraints for large files.
  3) Extended Retrieval Metadata (pages/chapters)
     - Ensure page_num is captured per chunk (existing) and introduce chapter metadata if needed.
  4) Upload Management UI
     - Enhance UI (ui/upload_tab.py) to display upload history, per-upload details, and delete option.
  5) Multi-tenancy & Permissions
     - Strengthen tenant-scoping in DB & APIs; ensure data separation across tenants.
  6) Testing & QA
     - Add unit tests for chunking, embedding calls, and basic integration path.
  7) Deployment & Operations
     - Migration planning, backups, staging verification, and roll-back strategy.

- Data Model Summary
  - uploads(id), documents(id, upload_id), doc_chunks(id, document_id, content, page_num, embedding, tenant_id, ...)
  - Relationships: uploads 1:N documents, documents 1:N doc_chunks.

- Migration Plan
  - Use existing migration: 20251204_alter_documents_upload_fk_cascade.sql to ensure FKs cascade on upload deletion.
  - Validation steps to verify cascade semantics in staging before production.

- Risk & Rollback
  - Risk: cascading deletes may remove data unintentionally in production; ensure backups and test coverage.
  - Rollback: revert FK to ON DELETE SET NULL via a new migration.

- Success Criteria
  - Upload can be processed and tracked; documents and chunks cascade on upload deletion; basic queries return expected results.

- Next Steps
  - Confirm plan or adjust priorities; after approval, proceed to PLAN MODE for a more detailed, itemized plan and then ACT MODE for implementation.

+Phase 2 — Upload history endpoints
+- GET /uploads: list uploads with id, title, owner, tenant_id, total_files, status, created_at
+- DELETE /uploads/{upload_id}: cascade delete of uploads -> documents -> doc_chunks
+- Tenant-scoped access: require tenant_id for listing/deletion

+Phase 3 — Asynchronous upload processing
+- ThreadPoolExecutor-based worker pool
+- Enqueue uploads; update status to processing and then to completed
+- Progress events to UI via uploads table
