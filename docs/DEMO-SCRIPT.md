# THE DEMO — Definition of Done (one continuous take)

Setup: Mac awake, menu-bar icon shows DORMANT. Room mic distance ~2m. Phone timer visible (proves no cuts).

| # | You say / do | Friday must do | Proves |
|---|---|---|---|
| 1 | Active wake phrase (dashboard header: "Hey Jarvis" fallback until "Hey Friday" is trained) | Chime + greeting. Menu-bar -> ACTIVE | Wake word, session start |
| 2 | "What did I quote the Receivly client last month?" | Correct answer from leos-brain vault, <= 3 sentences | Vault brain |
| 3 | "Remember: demo day was today and it went clean." | "Noted, sir." (fact lands in memory) | Memory write |
| 4 | "What's the weather today?" | Live Open-Meteo conditions, spoken | Local tool (safe) |
| 5 | "Put lunch with Sam on my calendar tomorrow at noon." | "Shall I proceed, sir?" -> you: "Yes." -> event appears in Calendar.app | Ops + confirm gate |
| 6 | "How's my job search going?" | Latest batch counts + what awaits you, from ~/Downloads/Jobs | Jobs command center |
| 7 | "Play some music on Spotify." | Spotify starts playing | Mac control |
| 8 | "Stand down." | Standing-down chime, menu-bar -> DORMANT | Kill path |

Redefined 2026-09-29: the old steps (content pipeline, screen recall, camera) depended
on features that were removed or parked. Rehearsed by machine in
tests/scenario/test_demo_script.py (steps 2-7, one thread, real tools.yaml).

PASS = all 8 steps clean, no touching keyboard/mouse after step 0, three runs in a row.
Next morning check: first wake of day triggers the spoken morning brief.

## Failure log
(record failed attempts here: date, step, cause, fix)
