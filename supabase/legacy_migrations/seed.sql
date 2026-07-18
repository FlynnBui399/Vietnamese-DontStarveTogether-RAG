insert into knowledge.embedding_models (
    id,
    model_key,
    provider,
    model_name,
    model_revision,
    dimensions,
    distance_metric,
    normalized,
    batch_size,
    is_active
)
values (
    '00000000-0000-0000-0000-000000000001',
    'fixture-hash-1024',
    'fixture',
    'deterministic-hash',
    '1',
    1024,
    'cosine',
    true,
    32,
    true
)
on conflict (model_key) do nothing;

insert into knowledge.corpus_versions (
    id,
    version,
    status,
    embedding_model_key,
    manifest
)
values (
    '00000000-0000-0000-0000-000000000002',
    'dev-fixture',
    'building',
    'fixture-hash-1024',
    '{"fixture": true}'::jsonb
)
on conflict (version) do nothing;

insert into knowledge.wiki_pages (
    id,
    mediawiki_page_id,
    title,
    slug,
    canonical_url,
    namespace,
    revision_id,
    content_hash,
    game_scope,
    entity_type,
    source_kind,
    metadata,
    is_active
)
values (
    '00000000-0000-0000-0000-000000000003',
    1,
    'Milestone Fixture',
    'milestone-fixture',
    'https://example.invalid/wiki/Milestone_Fixture',
    0,
    1,
    repeat('0', 64),
    'dst',
    'other',
    'factual_article',
    '{"fixture": true}'::jsonb,
    false
)
on conflict (mediawiki_page_id, revision_id) do nothing;

insert into knowledge.source_attributions (
    id,
    wiki_page_id,
    source_name,
    source_url,
    license_name,
    attribution_text,
    metadata
)
values (
    '00000000-0000-0000-0000-000000000004',
    '00000000-0000-0000-0000-000000000003',
    'Development fixture',
    'https://example.invalid/wiki/Milestone_Fixture',
    'Fixture only',
    'Synthetic test data; not wiki content.',
    '{"fixture": true}'::jsonb
)
on conflict (wiki_page_id, source_url) do nothing;
