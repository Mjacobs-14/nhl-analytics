# Interactive visualizations

Self-contained, single-file HTML pages — no server, no build, no network. Just
open any file in a browser (double-click, or `python -m http.server` in this
folder). Each embeds a **data snapshot** taken from the SQL views on the date
below, so they don't auto-update; re-export when you want fresh numbers.

Every page shares the same interactions: **season picker**, **team filter**
(default All NHL, league-fixed axes so teams are comparable), **forwards/defense
toggle**, **global player search** (finds anyone, including retired players, and
traces their career), **click a dot to trace a career**, a **table view**, and
light/dark theming.

| File | What it shows | Built from |
|------|---------------|------------|
| `shot_quadrants.html` | Shots on goal /60 vs points/game — volume vs. finishing | `player_shot_volume_output_v` |
| `coach_fingerprints.html` | Coach style (defense / offense / rush maps), style-over-time consistency, mid-season change turnarounds | `coach_style_v`, `coach_rush_v`, `coach_change_v` |
| `edge_athleticism.html` | NHL Edge skating — top speed vs bursts / distance | `player_athleticism_v` |
| `clutch.html` | Game-state scoring — clutch tilt vs production, per-player state fingerprints | `player_clutch_v` |
| `goalie_hot_hand.html` | Goalie streakiness vs quality, with click-to-open hot/cold start timelines | `goalie_streak_v`, `goalie_game_v` |
| `matchup_lab.html` | Two-team style-clash previews: road-vs-home attack mixes × concession profiles × goalie band SV% (with starter override), priced in expected goals | `team_shot_location_v`, `goalie_location_v` |

**Snapshot date:** 2026-07-14 (8 seasons, 2018–2026; Edge 2021–2026).

**Note on team assignment:** traded players are shown with their most-played
team that season, using full-season stats (the only consistent choice, since
Edge data is season-level and can't be split by team).

These are the prototype/handoff versions. The plan is to port them into the
Next.js app as live pages querying the views directly.
