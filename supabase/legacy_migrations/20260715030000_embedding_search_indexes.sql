create index if not exists document_chunks_embedding_hnsw_idx
on knowledge.document_chunks
using hnsw (embedding extensions.vector_cosine_ops);

comment on index knowledge.document_chunks_embedding_hnsw_idx is
'HNSW cosine index for 1024-dimensional chunk embeddings.';

create or replace function public.semantic_search_dst(
    p_corpus_version uuid,
    p_query_embedding extensions.vector(1024),
    p_match_count integer default 5
)
returns table (
    chunk_id uuid,
    page_title text,
    section_path text,
    cosine_distance double precision,
    similarity double precision
)
language sql
stable
security invoker
set search_path = ''
as $$
    select
        c.id,
        c.page_title,
        c.section_path,
        (c.embedding operator(extensions.<=>) p_query_embedding)::double precision,
        (1.0 - (c.embedding operator(extensions.<=>) p_query_embedding))::double precision
    from knowledge.document_chunks as c
    where c.corpus_version_id = p_corpus_version
      and c.game_scope = 'dst'
      and c.embedding is not null
    order by c.embedding operator(extensions.<=>) p_query_embedding
    limit least(greatest(p_match_count, 1), 100)
$$;

create or replace function public.lexical_search_dst(
    p_corpus_version uuid,
    p_query_text text,
    p_match_count integer default 5
)
returns table (
    chunk_id uuid,
    page_title text,
    section_path text,
    lexical_rank real
)
language sql
stable
security invoker
set search_path = ''
as $$
    select
        c.id,
        c.page_title,
        c.section_path,
        ts_rank_cd(c.fts, websearch_to_tsquery('simple', p_query_text))
    from knowledge.document_chunks as c
    where c.corpus_version_id = p_corpus_version
      and c.game_scope = 'dst'
      and c.fts @@ websearch_to_tsquery('simple', p_query_text)
    order by ts_rank_cd(c.fts, websearch_to_tsquery('simple', p_query_text)) desc, c.id
    limit least(greatest(p_match_count, 1), 100)
$$;

revoke all on function public.semantic_search_dst(uuid, extensions.vector, integer)
from public, anon, authenticated;
revoke all on function public.lexical_search_dst(uuid, text, integer)
from public, anon, authenticated;

grant execute on function public.semantic_search_dst(uuid, extensions.vector, integer)
to service_role;
grant execute on function public.lexical_search_dst(uuid, text, integer)
to service_role;
