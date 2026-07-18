create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists unaccent with schema extensions;

create schema if not exists knowledge;

revoke all on schema knowledge from public, anon, authenticated;
grant usage on schema knowledge to service_role;

create table knowledge.embedding_models (
    id uuid primary key default gen_random_uuid(),
    model_key text not null unique check (btrim(model_key) <> ''),
    provider text not null check (btrim(provider) <> ''),
    model_name text not null check (btrim(model_name) <> ''),
    model_revision text,
    dimensions integer not null check (dimensions > 0),
    distance_metric text not null default 'cosine'
        check (distance_metric in ('cosine', 'inner_product', 'l2')),
    normalized boolean not null default true,
    batch_size integer not null default 32 check (batch_size > 0),
    created_at timestamptz not null default now(),
    is_active boolean not null default false
);

create unique index one_active_embedding_model
on knowledge.embedding_models ((is_active))
where is_active;

create table knowledge.corpus_versions (
    id uuid primary key default gen_random_uuid(),
    version text not null unique check (btrim(version) <> ''),
    status text not null check (
        status in ('building', 'validating', 'active', 'failed', 'archived')
    ),
    embedding_model_key text not null
        references knowledge.embedding_models(model_key),
    page_count integer not null default 0 check (page_count >= 0),
    chunk_count integer not null default 0 check (chunk_count >= 0),
    source_revision_max bigint,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    activated_at timestamptz,
    manifest jsonb not null default '{}'::jsonb
        check (jsonb_typeof(manifest) = 'object')
);

create unique index one_active_corpus_version
on knowledge.corpus_versions ((status))
where status = 'active';

create table knowledge.wiki_pages (
    id uuid primary key default gen_random_uuid(),
    mediawiki_page_id bigint not null,
    title text not null check (btrim(title) <> ''),
    slug text,
    canonical_url text not null check (canonical_url ~ '^https://'),
    namespace integer not null default 0,
    revision_id bigint not null,
    revision_timestamp timestamptz,
    retrieved_at timestamptz not null default now(),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    game_scope text not null check (
        game_scope in (
            'dst', 'dont_starve', 'reign_of_giants', 'shipwrecked',
            'hamlet', 'mixed', 'unknown'
        )
    ),
    entity_type text check (
        entity_type is null or entity_type in (
            'character', 'item', 'weapon', 'armor', 'tool', 'food', 'recipe',
            'structure', 'mob', 'boss', 'mechanic', 'biome', 'season', 'guide',
            'update', 'other'
        )
    ),
    source_kind text check (
        source_kind is null or source_kind in (
            'factual_article', 'guide', 'version_history', 'category_list', 'unknown'
        )
    ),
    language text not null default 'en',
    raw_storage_bucket text,
    raw_storage_path text,
    is_active boolean not null default true,
    metadata jsonb not null default '{}'::jsonb
        check (jsonb_typeof(metadata) = 'object'),
    unique (mediawiki_page_id, revision_id)
);

create table knowledge.document_chunks (
    id uuid primary key default gen_random_uuid(),
    corpus_version_id uuid not null
        references knowledge.corpus_versions(id) on delete cascade,
    wiki_page_id uuid not null
        references knowledge.wiki_pages(id) on delete cascade,
    source_key text not null unique check (source_key ~ '^[0-9a-f]{64}$'),
    page_title text not null check (btrim(page_title) <> ''),
    section_path text not null check (btrim(section_path) <> ''),
    chunk_index integer not null check (chunk_index >= 0),
    content text not null check (btrim(content) <> ''),
    content_normalized text not null check (btrim(content_normalized) <> ''),
    content_hash text not null check (content_hash ~ '^[0-9a-f]{64}$'),
    token_count integer not null check (token_count > 0),
    game_scope text not null check (
        game_scope in (
            'dst', 'dont_starve', 'reign_of_giants', 'shipwrecked',
            'hamlet', 'mixed', 'unknown'
        )
    ),
    entity_type text check (
        entity_type is null or entity_type in (
            'character', 'item', 'weapon', 'armor', 'tool', 'food', 'recipe',
            'structure', 'mob', 'boss', 'mechanic', 'biome', 'season', 'guide',
            'update', 'other'
        )
    ),
    source_kind text not null check (
        source_kind in (
            'factual_article', 'guide', 'version_history', 'category_list', 'unknown'
        )
    ),
    subjective boolean not null default false,
    canonical_url text not null check (canonical_url ~ '^https://'),
    revision_id bigint not null,
    search_text text not null check (btrim(search_text) <> ''),
    fts tsvector generated always as (
        to_tsvector('simple', coalesce(search_text, ''))
    ) stored,
    embedding extensions.vector(1024),
    metadata jsonb not null default '{}'::jsonb
        check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now(),
    unique (corpus_version_id, wiki_page_id, section_path, chunk_index)
);

comment on column knowledge.document_chunks.embedding is
'1024-dimensional vector. Changing dimensions requires a versioned migration and a rebuilt corpus.';

create table knowledge.entity_aliases (
    id uuid primary key default gen_random_uuid(),
    entity_title text not null check (btrim(entity_title) <> ''),
    entity_slug text,
    alias text not null check (btrim(alias) <> ''),
    alias_normalized text not null check (btrim(alias_normalized) <> ''),
    language text not null check (btrim(language) <> ''),
    alias_type text not null check (
        alias_type in (
            'official_title', 'official_translation', 'community_translation',
            'abbreviation', 'common_misspelling', 'descriptive_alias',
            'generated_candidate'
        )
    ),
    priority integer not null default 0,
    confidence numeric(5, 4) check (confidence between 0 and 1),
    verified boolean not null default false,
    source text,
    metadata jsonb not null default '{}'::jsonb
        check (jsonb_typeof(metadata) = 'object'),
    unique (entity_title, alias_normalized)
);

create table knowledge.source_attributions (
    id uuid primary key default gen_random_uuid(),
    wiki_page_id uuid not null
        references knowledge.wiki_pages(id) on delete cascade,
    source_name text not null check (btrim(source_name) <> ''),
    source_url text not null check (source_url ~ '^https://'),
    license_name text,
    attribution_text text,
    metadata jsonb not null default '{}'::jsonb
        check (jsonb_typeof(metadata) = 'object'),
    unique (wiki_page_id, source_url)
);

create table knowledge.sync_runs (
    id uuid primary key default gen_random_uuid(),
    status text not null check (
        status in ('running', 'succeeded', 'failed', 'cancelled')
    ),
    sync_type text not null check (
        sync_type in ('initial', 'incremental', 'rebuild_embeddings')
    ),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    pages_discovered integer not null default 0 check (pages_discovered >= 0),
    pages_fetched integer not null default 0 check (pages_fetched >= 0),
    pages_changed integer not null default 0 check (pages_changed >= 0),
    chunks_created integer not null default 0 check (chunks_created >= 0),
    error_count integer not null default 0 check (error_count >= 0),
    details jsonb not null default '{}'::jsonb
        check (jsonb_typeof(details) = 'object')
);

create index document_chunks_fts_idx
on knowledge.document_chunks using gin (fts);

create index document_chunks_scope_idx
on knowledge.document_chunks (game_scope, entity_type);

create index document_chunks_corpus_idx
on knowledge.document_chunks (corpus_version_id);

create index wiki_pages_mediawiki_id_idx
on knowledge.wiki_pages (mediawiki_page_id);

create index wiki_pages_revision_idx
on knowledge.wiki_pages (revision_id);

create index entity_aliases_normalized_trgm_idx
on knowledge.entity_aliases
using gin (alias_normalized extensions.gin_trgm_ops);

alter table knowledge.embedding_models enable row level security;
alter table knowledge.corpus_versions enable row level security;
alter table knowledge.wiki_pages enable row level security;
alter table knowledge.document_chunks enable row level security;
alter table knowledge.entity_aliases enable row level security;
alter table knowledge.source_attributions enable row level security;
alter table knowledge.sync_runs enable row level security;

revoke all privileges on all tables in schema knowledge from anon, authenticated;
revoke all privileges on all sequences in schema knowledge from anon, authenticated;
grant all privileges on all tables in schema knowledge to service_role;
grant all privileges on all sequences in schema knowledge to service_role;

alter default privileges in schema knowledge
revoke all privileges on tables from anon, authenticated;
alter default privileges in schema knowledge
revoke all privileges on sequences from anon, authenticated;
alter default privileges in schema knowledge
grant all privileges on tables to service_role;
alter default privileges in schema knowledge
grant all privileges on sequences to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
    (
        'dst-wiki-raw',
        'dst-wiki-raw',
        false,
        52428800,
        array['application/json', 'text/html']
    ),
    (
        'dst-corpus-snapshots',
        'dst-corpus-snapshots',
        false,
        52428800,
        array['application/json', 'application/gzip', 'application/x-gzip']
    ),
    (
        'dst-evaluation-reports',
        'dst-evaluation-reports',
        false,
        10485760,
        array['application/json', 'text/markdown', 'text/plain']
    )
on conflict (id) do update set
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

