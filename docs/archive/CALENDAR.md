# Calendar — Phase D2

Friday reads and books your calendar through **macOS EventKit** — whatever
Calendar.app shows, Friday sees. Google Calendar included, IF the Google
account is added in Calendar.app (Settings → Accounts). No Google API, no
tokens on disk.

## One-time setup

1. First calendar use (say "what's on my calendar today?" or run
   `make collect`) triggers the macOS **Calendar permission prompt** — allow
   Full Access. If you miss it: System Settings → Privacy & Security →
   Calendars.
2. Want Google events? Add the account to Calendar.app. Done.

## By voice

| You say | What happens |
|---|---|
| "What's on my calendar today?" | `calendar_today` (safe) reads the day aloud |
| "Book a meeting with the dentist tomorrow at 3pm" | `calendar_event` parses title/time, then **"Shall I proceed, sir?"** — nothing lands without a spoken yes |
| "How did the reels do this week?" | `metrics_report` (safe) reads the Mission Board aloud |

No clear date+time in a booking request → Friday refuses rather than guesses.
Every execution is audited; the morning brief now leads with your first event;
the board gains a `calendar` card (events today) on each collect sweep.

All three live in `config/tools.yaml` — the router learns them from their
descriptions; nothing in the brain was rewired.
