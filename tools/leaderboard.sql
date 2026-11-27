-- NFL Golf daily leaderboard. Paste into Supabase → SQL Editor → Run.
-- The page uses the project's public anon key; row-level security below is what limits it:
-- anyone can read today's scores and add one score per device per day, nobody can edit or delete.

create table if not exists public.daily_scores (
  id         bigint generated always as identity primary key,
  day        date        not null,
  name       text        not null check (char_length(btrim(name)) between 1 and 20),
  score      numeric(5,1) not null check (score between 0 and 900),
  to_par     smallint    check (to_par between -27 and 45),  -- golf score for the 9 holes (ranked on this)
  hard       boolean     not null default false,  -- played in Hard mode (pin stat hidden)
  device     uuid        not null,
  created_at timestamptz not null default now(),
  unique (day, device)
);

create index if not exists daily_scores_day_score on public.daily_scores (day, score, created_at);

-- Added when scoring switched to strokes vs par (safe to re-run; does nothing if the column exists).
alter table public.daily_scores add column if not exists to_par smallint check (to_par between -27 and 45);

alter table public.daily_scores enable row level security;

drop policy if exists "read scores" on public.daily_scores;
create policy "read scores" on public.daily_scores
  for select to anon using (true);

-- Only today's course (US Eastern), or yesterday's for rounds finished just after midnight.
drop policy if exists "post today's score" on public.daily_scores;
create policy "post today's score" on public.daily_scores
  for insert to anon
  with check (day between (now() at time zone 'America/New_York')::date - 1
                      and (now() at time zone 'America/New_York')::date);

grant select, insert on public.daily_scores to anon;
