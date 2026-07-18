create or replace function public.hybrid_search_dst(
    p_query_text text,
    p_query_embedding extensions.vector(1024),
    p_match_count integer default 30,
    p_lexical_count integer default 40,
    p_semantic_count integer default 40,
    p_filter_entity_type text default null,
    p_entity_titles text[] default null,
    p_section_intent text default null,
    p_rrf_k integer default 60
)
returns table (
    chunk_id uuid,
    corpus_version_id uuid,
    page_title text,
    section_path text,
    content text,
    content_hash text,
    token_count integer,
    game_scope text,
    entity_type text,
    source_kind text,
    subjective boolean,
    canonical_url text,
    revision_id bigint,
    metadata jsonb,
    lexical_rank bigint,
    semantic_rank bigint,
    cosine_similarity double precision,
    rrf_score double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
    with active_corpus as (
        select id
        from knowledge.corpus_versions
        where status = 'active'
        limit 1
    ),
    lexical_candidates as (
        select
            c.id,
            ts_rank_cd(c.fts, websearch_to_tsquery('simple', p_query_text)) as lexical_score
        from knowledge.document_chunks as c
        join active_corpus as active on active.id = c.corpus_version_id
        where c.game_scope = 'dst'
          and c.fts @@ websearch_to_tsquery('simple', p_query_text)
          and (p_filter_entity_type is null or c.entity_type = p_filter_entity_type)
        order by lexical_score desc, c.id
        limit least(greatest(p_lexical_count, 1), 200)
    ),
    lexical as (
        select
            id,
            row_number() over (order by lexical_score desc, id) as rank
        from lexical_candidates
    ),
    semantic_candidates as (
        select
            c.id,
            c.embedding operator(extensions.<=>) p_query_embedding as cosine_distance
        from knowledge.document_chunks as c
        join active_corpus as active on active.id = c.corpus_version_id
        where c.game_scope = 'dst'
          and c.embedding is not null
          and (p_filter_entity_type is null or c.entity_type = p_filter_entity_type)
        order by c.embedding operator(extensions.<=>) p_query_embedding, c.id
        limit least(greatest(p_semantic_count, 1), 200)
    ),
    semantic as (
        select
            id,
            cosine_distance,
            row_number() over (order by cosine_distance, id) as rank
        from semantic_candidates
    ),
    combined as (
        select
            coalesce(lexical.id, semantic.id) as id,
            lexical.rank as lexical_rank,
            semantic.rank as semantic_rank,
            semantic.cosine_distance,
            coalesce(1.0 / (greatest(p_rrf_k, 1) + lexical.rank), 0.0)
            + coalesce(1.0 / (greatest(p_rrf_k, 1) + semantic.rank), 0.0)
            as base_score
        from lexical
        full outer join semantic on semantic.id = lexical.id
    ),
    scored as (
        select
            c.*,
            combined.lexical_rank,
            combined.semantic_rank,
            combined.cosine_distance,
            combined.base_score
            + case
                when p_entity_titles is not null and c.page_title = any(p_entity_titles)
                    then 0.020
                else 0.0
              end
            + case
                when p_section_intent is not null
                 and c.section_path ilike ('%' || p_section_intent || '%')
                    then 0.005
                else 0.0
              end as final_score
        from combined
        join knowledge.document_chunks as c on c.id = combined.id
    )
    select
        scored.id,
        scored.corpus_version_id,
        scored.page_title,
        scored.section_path,
        scored.content,
        scored.content_hash,
        scored.token_count,
        scored.game_scope,
        scored.entity_type,
        scored.source_kind,
        scored.subjective,
        scored.canonical_url,
        scored.revision_id,
        scored.metadata,
        scored.lexical_rank,
        scored.semantic_rank,
        case
            when scored.cosine_distance is null then null
            else 1.0 - scored.cosine_distance
        end,
        scored.final_score
    from scored
    order by scored.final_score desc,
             scored.cosine_distance asc nulls last,
             scored.id
    limit least(greatest(p_match_count, 1), 100)
$$;

revoke all on function public.hybrid_search_dst(
    text,
    extensions.vector,
    integer,
    integer,
    integer,
    text,
    text[],
    text,
    integer
) from public, anon, authenticated;

grant execute on function public.hybrid_search_dst(
    text,
    extensions.vector,
    integer,
    integer,
    integer,
    text,
    text[],
    text,
    integer
) to service_role;

comment on function public.hybrid_search_dst(
    text,
    extensions.vector,
    integer,
    integer,
    integer,
    text,
    text[],
    text,
    integer
) is 'Backend-only active-corpus DST retrieval using FTS, cosine search, RRF, and bounded boosts.';
