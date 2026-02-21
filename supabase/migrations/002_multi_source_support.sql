-- ============================================================
-- Migration 002: Multi-Source Support for SC Website Scraper
--
-- Adds support for Supreme Court daily orders as a second
-- data source alongside Indian Kanoon API.
-- ============================================================

-- 1. Add source tracking to judgments (backward-compatible default)
ALTER TABLE judgments ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'ik_api'
    CHECK (source IN ('ik_api', 'sc_website'));

-- 2. Make ik_doc_id nullable (SC orders won't have IK doc IDs)
ALTER TABLE judgments ALTER COLUMN ik_doc_id DROP NOT NULL;

-- 3. Add SC-specific identifier
ALTER TABLE judgments ADD COLUMN sc_case_number VARCHAR(100);

-- 4. Add external URL for SC PDF links
--    (ik_url is auto-generated from ik_doc_id, which will be NULL for SC orders)
ALTER TABLE judgments ADD COLUMN external_url TEXT;

-- 5. Add full-text column for SC order text extracted from PDF
ALTER TABLE judgments ADD COLUMN full_text TEXT;

-- 6. Partial unique index for SC dedup: (sc_case_number, judgment_date) where source = sc_website
CREATE UNIQUE INDEX idx_judgments_sc_dedup
    ON judgments (sc_case_number, judgment_date)
    WHERE source = 'sc_website' AND sc_case_number IS NOT NULL;

-- 7. GIN trigram index on full_text for future full-text search
CREATE INDEX idx_judgments_full_text_trgm
    ON judgments USING gin (full_text extensions.gin_trgm_ops)
    WHERE full_text IS NOT NULL;

-- 8. Index on source for filtered queries
CREATE INDEX idx_judgments_source ON judgments(source);
