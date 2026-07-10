-- ============================================================
-- Venue capacities (hockey configuration) + attendance-% view.
--
-- Keyed on the exact venue strings the boxscore API uses, so arena
-- renames (BB&T -> FLA Live -> Amerant) and relocations (Gila River ->
-- Mullett -> Delta Center) each carry their own row and era. One-off
-- venues (outdoor stadiums, international sites, preseason minors)
-- are deliberately left out — sellout % is meaningless for them; their
-- games simply get a null attendance_pct.
--
-- Capacities are the commonly published hockey-configuration figures;
-- treat attendance_pct as approximate (COVID-era caps make 2020-21
-- percentages historically tiny — that's real, not a bug).
--
-- Idempotent — safe to re-run (upserts).
-- ============================================================

create table if not exists venues (
    venue    text primary key,   -- exact string from games.venue
    capacity int not null
);

insert into venues (venue, capacity) values
    ('Amalie Arena', 19092), ('Benchmark International Arena', 19092),
    ('Amerant Bank Arena', 19250), ('FLA Live Arena', 19250), ('BB&T Center', 19250),
    ('American Airlines Center', 18532),
    ('Ball Arena', 17809), ('Pepsi Center', 17809),
    ('Bell Centre', 21105), ('Centre Bell', 21105),
    ('Bridgestone Arena', 17159),
    ('Canada Life Centre', 15321), ('Bell MTS Place', 15321),
    ('Canadian Tire Centre', 18652),
    ('Capital One Arena', 18573),
    ('Climate Pledge Arena', 17151),
    ('Crypto.com Arena', 18230), ('STAPLES Center', 18230),
    ('Delta Center', 16020), ('Vivint Arena', 16020),
    ('Enterprise Center', 18096),
    ('Gila River Arena', 17125),
    ('Grand Casino Arena', 17954), ('Xcel Energy Center', 17954),
    ('Honda Center', 17174),
    ('KeyBank Center', 19070),
    ('Lenovo Center', 18680), ('PNC Arena', 18680),
    ('Little Caesars Arena', 19515),
    ('Madison Square Garden', 18006),
    ('Mullett Arena', 4600),
    ('Nationwide Arena', 18500),
    ('NYCB Live/Nassau Coliseum', 13917), ('Nassau Veterans Memorial Coliseum', 13917),
    ('Barclays Center', 15795),
    ('PPG Paints Arena', 18387),
    ('Prudential Center', 16514),
    ('Rogers Arena', 18910),
    ('Rogers Place', 18347),
    ('SAP Center at San Jose', 17562),
    ('Scotiabank Arena', 18819),
    ('Scotiabank Saddledome', 19289),
    ('T-Mobile Arena', 17500),
    ('TD Garden', 17850),
    ('UBS Arena', 17255),
    ('United Center', 19717),
    ('Wells Fargo Center', 19543), ('Xfinity Mobile Arena', 19543)
on conflict (venue) do update set capacity = excluded.capacity;

create or replace view game_attendance_v as
select
    g.game_id,
    g.game_date,
    g.season,
    g.game_type,
    g.venue,
    g.attendance,
    v.capacity,
    case when v.capacity > 0 and g.attendance is not null
         then round(g.attendance::numeric / v.capacity, 3)
         else null end as attendance_pct,
    g.temp_c,
    g.precip_mm,
    g.snowfall_cm,
    g.humidity_pct
from games g
left join venues v on v.venue = g.venue;
