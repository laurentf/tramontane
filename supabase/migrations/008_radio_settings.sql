-- Radio station settings per user
create table if not exists radio_settings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  station_name text not null default 'Tramontane',
  language text not null default 'fr' check (language in ('en', 'fr', 'es')),
  location text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id)
);

-- Updated-at trigger (reuses trigger function from migration 004)
create trigger set_updated_at
  before update on radio_settings
  for each row execute function set_updated_at();

-- RLS
alter table radio_settings enable row level security;

create policy "Users can read own settings"
  on radio_settings for select
  using (auth.uid() = user_id);

create policy "Users can insert own settings"
  on radio_settings for insert
  with check (auth.uid() = user_id);

create policy "Users can update own settings"
  on radio_settings for update
  using (auth.uid() = user_id);
