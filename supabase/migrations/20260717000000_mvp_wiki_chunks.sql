create extension if not exists vector with schema extensions;

create table if not exists public.wiki_chunks (
    id text primary key,
    page_title text not null,
    section text not null,
    content text not null,
    url text not null,
    revision_id bigint not null,
    embedding extensions.vector(1024) not null,
    updated_at timestamptz not null default now()
);

alter table public.wiki_chunks enable row level security;

create index if not exists wiki_chunks_embedding_hnsw_idx
on public.wiki_chunks
using hnsw (embedding extensions.vector_cosine_ops);

create or replace function public.match_wiki_chunks(
    query_embedding extensions.vector(1024),
    match_count integer default 5,
    min_similarity double precision default 0.20
)
returns table (
    id text,
    page_title text,
    section text,
    content text,
    url text,
    similarity double precision
)
language sql
stable
security definer
set search_path = ''
as $$
    select
        c.id,
        c.page_title,
        c.section,
        c.content,
        c.url,
        (1.0 - (c.embedding operator(extensions.<=>) query_embedding))::double precision
    from public.wiki_chunks as c
    where (1.0 - (c.embedding operator(extensions.<=>) query_embedding)) >= min_similarity
    order by c.embedding operator(extensions.<=>) query_embedding
    limit least(greatest(match_count, 1), 20)
$$;

revoke all on table public.wiki_chunks from public, anon, authenticated;
revoke all on function public.match_wiki_chunks(extensions.vector, integer, double precision)
from public, anon, authenticated;

grant select, insert, update, delete on table public.wiki_chunks to service_role;
grant execute on function public.match_wiki_chunks(
    extensions.vector,
    integer,
    double precision
) to service_role;
