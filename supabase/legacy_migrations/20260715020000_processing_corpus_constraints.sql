alter table knowledge.document_chunks
drop constraint if exists document_chunks_source_key_key;

create unique index if not exists document_chunks_corpus_source_key_idx
on knowledge.document_chunks (corpus_version_id, source_key);

comment on column knowledge.document_chunks.source_key is
'Deterministic identity derived from page, revision, section, chunk index, and content. It may recur in different corpus versions.';
