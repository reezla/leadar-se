-- Post-crawl product analysis: which Norrpoint scanner(s) to recommend per company.
alter table public.companies
  add column if not exists recommended_product text,
  add column if not exists alternative_products text[] not null default '{}',
  add column if not exists buyer_type text,
  add column if not exists customer_fit text,
  add column if not exists product_analysis jsonb,
  add column if not exists analyzed_at timestamptz;

alter table public.companies
  drop constraint if exists companies_customer_fit_values,
  add constraint companies_customer_fit_values
    check (customer_fit is null or customer_fit in ('weak', 'moderate', 'strong'));

alter table public.companies
  drop constraint if exists companies_buyer_type_values,
  add constraint companies_buyer_type_values
    check (
      buyer_type is null
      or buyer_type in ('performs_measurement', 'orders_measurement', 'not_relevant', 'unknown')
    );

create index if not exists companies_recommended_product_idx
  on public.companies (recommended_product);

create index if not exists companies_customer_fit_idx
  on public.companies (customer_fit);
