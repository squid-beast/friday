/* friday-ui · lib/stores.js — shared state: the status payload every screen
   reads (header, NOW panel), refreshed on one 60s interval from +layout. */
import { writable } from "svelte/store";
import { systemStatus } from "$lib/api.js";

export const status = writable({
  daemon: "off",
  identity: {
    assistant: "Friday",
    wake_phrase: "Hey Friday",
    wake_phrase_active: "Hey Jarvis",
    wake_phrase_ready: false,
    stand_down_phrase: "Stand Down",
    voice_lock: "open",
    voice_lock_ready: false,
    voice_lock_scope: "wake-only",
  },
  systems: {},
  queue: 0,
  next_event: null,
  activity: [],
});
export async function refreshPanels() {
  try { status.set(await systemStatus()); } catch { /* panel keeps last state */ }
}
