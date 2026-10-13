create table public.companies (
  organization_number text primary key,
  name text not null,
  workplace_name text,
  sni_codes text[] not null default '{}',
  activity_description text,
  municipality text,
  county text,
  postal_address text,
  employee_class text,
  employee_min integer,
  employee_max integer,
  revenue_class text,
  revenue_min_sek bigint,
  revenue_max_sek bigint,
  active boolean not null default true,
  source text not null default 'SCB Företagsregistret',
  retrieved_at timestamptz not null default now(),
  score integer,
  score_reasons jsonb not null default '[]'::jsonb,
  missing_data text[] not null default '{}',
  domain text,
  about_text text,
  projects_text text,
  pages_fetched text[] not null default '{}',
  website_source text,
  suggested_recipient text,
  crawl_status text,
  crawl_detail text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint companies_organization_number_digits check (organization_number ~ '^[0-9]{10}$')
);

create table public.company_searches (
  id bigint generated always as identity primary key,
  query_key text not null unique,
  segment_key text not null,
  sni_prefixes text[] not null default '{}',
  counties text[] not null default '{}',
  municipalities text[] not null default '{}',
  employee_min integer,
  employee_max integer,
  revenue_min_sek bigint,
  revenue_max_sek bigint,
  active_only boolean not null default true,
  text_query text,
  result_limit integer,
  fetched_count integer not null default 0,
  matched_count integer not null default 0,
  saved_count integer not null default 0,
  first_searched_at timestamptz not null default now(),
  last_searched_at timestamptz not null default now(),
  run_count integer not null default 1,
  constraint company_searches_run_count_positive check (run_count >= 1)
);

create index company_searches_last_searched_at_idx
  on public.company_searches (last_searched_at desc);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger companies_set_updated_at
before update on public.companies
for each row
execute function public.set_updated_at();

alter table public.companies enable row level security;
alter table public.company_searches enable row level security;

revoke all on table public.companies from public, anon, authenticated;
revoke all on table public.company_searches from public, anon, authenticated;
revoke all on function public.set_updated_at() from public;

grant select, insert, update on table public.companies to service_role;
grant select, insert, update on table public.company_searches to service_role;
grant usage, select on sequence public.company_searches_id_seq to service_role;
