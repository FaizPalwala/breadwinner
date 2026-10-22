-- Migration 002: Add contract_path, ats_score, xyz_score, domain_recall_score, and provenance_status
ALTER TABLE jobs ADD COLUMN contract_path TEXT;
ALTER TABLE jobs ADD COLUMN ats_score INTEGER;
ALTER TABLE jobs ADD COLUMN xyz_score INTEGER;
ALTER TABLE jobs ADD COLUMN domain_recall_score INTEGER;
ALTER TABLE jobs ADD COLUMN provenance_status TEXT DEFAULT 'unverified';

-- Migrate existing match_score values into ats_score
UPDATE jobs SET ats_score = match_score WHERE ats_score IS NULL;
