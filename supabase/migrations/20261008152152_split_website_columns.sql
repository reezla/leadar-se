alter table public.companies
  add column if not exists about_text text,
  add column if not exists projects_text text,
  add column if not exists pages_fetched text[] not null default '{}',
  add column if not exists website_source text,
  add column if not exists suggested_recipient text;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'companies'
      and column_name = 'website'
  ) then
    update public.companies
    set
      about_text = website ->> 'about_text',
      projects_text = website ->> 'projects_text',
      pages_fetched = case
        when jsonb_typeof(website -> 'pages_fetched') = 'array'
        then array(select jsonb_array_elements_text(website -> 'pages_fetched'))
        else pages_fetched
      end,
      website_source = website ->> 'source',
      suggested_recipient = website ->> 'suggested_recipient'
    where website is not null;

    alter table public.companies drop column website;
  end if;
end $$;
