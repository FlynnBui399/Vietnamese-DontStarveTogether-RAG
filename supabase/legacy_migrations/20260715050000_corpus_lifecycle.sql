create or replace function knowledge.corpus_readiness(
    p_corpus_id uuid,
    p_require_current_revisions boolean default true
)
returns table (
    ready boolean,
    issues text[],
    actual_page_count bigint,
    actual_chunk_count bigint,
    missing_embedding_count bigint,
    stale_revision_count bigint
)
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
    target knowledge.corpus_versions%rowtype;
    active_page_count bigint;
    invalid_metadata_count bigint;
    findings text[] := array[]::text[];
begin
    select * into target
    from knowledge.corpus_versions
    where id = p_corpus_id;

    if target.id is null then
        raise exception 'Corpus % does not exist', p_corpus_id;
    end if;

    select count(*) into active_page_count
    from knowledge.wiki_pages
    where is_active;

    select
        count(distinct c.wiki_page_id),
        count(*),
        count(*) filter (where c.embedding is null),
        count(*) filter (where not p.is_active),
        count(*) filter (
            where btrim(c.page_title) = ''
               or btrim(c.section_path) = ''
               or btrim(c.content) = ''
               or btrim(c.canonical_url) = ''
               or c.revision_id is null
               or c.game_scope is null
        )
    into
        actual_page_count,
        actual_chunk_count,
        missing_embedding_count,
        stale_revision_count,
        invalid_metadata_count
    from knowledge.document_chunks as c
    join knowledge.wiki_pages as p on p.id = c.wiki_page_id
    where c.corpus_version_id = p_corpus_id;

    if target.status not in ('validating', 'archived') then
        findings := array_append(findings, 'status_not_validating_or_archived');
    end if;
    if target.manifest ->> 'processing_status' <> 'passed' then
        findings := array_append(findings, 'processing_not_passed');
    end if;
    if target.manifest ->> 'embedding_status' <> 'passed' then
        findings := array_append(findings, 'embedding_not_passed');
    end if;
    if actual_chunk_count = 0 or actual_chunk_count <> target.chunk_count then
        findings := array_append(findings, 'chunk_count_mismatch');
    end if;
    if actual_page_count <> target.page_count then
        findings := array_append(findings, 'page_coverage_mismatch');
    end if;
    if p_require_current_revisions and actual_page_count <> active_page_count then
        findings := array_append(findings, 'current_page_coverage_mismatch');
    end if;
    if missing_embedding_count > 0 then
        findings := array_append(findings, 'missing_embeddings');
    end if;
    if p_require_current_revisions and stale_revision_count > 0 then
        findings := array_append(findings, 'stale_revisions');
    end if;
    if invalid_metadata_count > 0 then
        findings := array_append(findings, 'invalid_chunk_metadata');
    end if;

    ready := cardinality(findings) = 0;
    issues := findings;
    return next;
end;
$$;

create or replace function public.activate_corpus_version(p_version text)
returns table (
    active_version text,
    archived_version text,
    activated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    target knowledge.corpus_versions%rowtype;
    previous knowledge.corpus_versions%rowtype;
    validation record;
    activation_time timestamptz := now();
begin
    select * into target
    from knowledge.corpus_versions
    where version = p_version
    for update;

    if target.id is null then
        raise exception 'Corpus version % does not exist', p_version;
    end if;
    if target.status <> 'validating' then
        raise exception 'Corpus version % must be validating, not %', p_version, target.status;
    end if;

    select * into validation from knowledge.corpus_readiness(target.id, true);
    if not validation.ready then
        raise exception 'Corpus version % is not ready: %', p_version, validation.issues;
    end if;

    select * into previous
    from knowledge.corpus_versions
    where status = 'active'
    for update;

    if previous.id is not null then
        update knowledge.corpus_versions
        set status = 'archived'
        where id = previous.id;
    end if;

    update knowledge.corpus_versions
    set
        status = 'active',
        activated_at = activation_time,
        completed_at = coalesce(completed_at, activation_time),
        manifest = manifest || jsonb_build_object(
            'activation', jsonb_build_object(
                'activated_at', activation_time,
                'previous_corpus_id', previous.id,
                'previous_version', previous.version
            )
        )
    where id = target.id;

    active_version := target.version;
    archived_version := previous.version;
    activated_at := activation_time;
    return next;
end;
$$;

create or replace function public.rollback_corpus_version(p_version text)
returns table (
    active_version text,
    archived_version text,
    activated_at timestamptz
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    target knowledge.corpus_versions%rowtype;
    current_active knowledge.corpus_versions%rowtype;
    validation record;
    rollback_time timestamptz := now();
begin
    select * into target
    from knowledge.corpus_versions
    where version = p_version
    for update;

    if target.id is null then
        raise exception 'Corpus version % does not exist', p_version;
    end if;
    if target.status <> 'archived' then
        raise exception 'Rollback target % must be archived, not %', p_version, target.status;
    end if;

    select * into validation from knowledge.corpus_readiness(target.id, false);
    if not validation.ready then
        raise exception 'Rollback target % is not ready: %', p_version, validation.issues;
    end if;

    select * into current_active
    from knowledge.corpus_versions
    where status = 'active'
    for update;

    if current_active.id is null then
        raise exception 'No active corpus exists to roll back';
    end if;

    update knowledge.corpus_versions
    set status = 'archived'
    where id = current_active.id;

    update knowledge.corpus_versions
    set
        status = 'active',
        activated_at = rollback_time,
        manifest = manifest || jsonb_build_object(
            'rollback', jsonb_build_object(
                'rolled_back_at', rollback_time,
                'replaced_corpus_id', current_active.id,
                'replaced_version', current_active.version
            )
        )
    where id = target.id;

    active_version := target.version;
    archived_version := current_active.version;
    activated_at := rollback_time;
    return next;
end;
$$;

revoke all on function knowledge.corpus_readiness(uuid, boolean) from public, anon, authenticated;
revoke all on function public.activate_corpus_version(text) from public, anon, authenticated;
revoke all on function public.rollback_corpus_version(text) from public, anon, authenticated;

grant execute on function knowledge.corpus_readiness(uuid, boolean) to service_role;
grant execute on function public.activate_corpus_version(text) to service_role;
grant execute on function public.rollback_corpus_version(text) to service_role;

comment on function public.activate_corpus_version(text) is
'Atomically validates and activates one complete corpus while archiving the previous active version.';

comment on function public.rollback_corpus_version(text) is
'Atomically validates and restores one archived corpus while archiving the current active version.';
