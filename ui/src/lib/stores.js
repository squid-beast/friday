/* friday-ui · lib/stores.js — shared state. The transcript lives HERE so it
   survives client-side navigation between the cockpit and the focused views. */
import { writable } from "svelte/store";
import { converse, systemStatus, studioQueue } from "$lib/api.js";

export const messages = writable([]);
export const busy = writable(false);

export async function say(text) {
  messages.update((m) => [...m, { who: "me", text }]);
  busy.set(true);
  try {
    const data = await converse(text);
    messages.update((m) => [...m,
      { who: "friday", text: data.reply, pending: !!data.pending }]);
  } catch {
    messages.update((m) => [...m,
      { who: "friday", text: "I can't reach the house, sir." }]);
  } finally {
    busy.set(false);
  }
}

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
export const queue = writable({ items: [], armed: false });

export async function refreshPanels() {
  try { status.set(await systemStatus()); } catch { /* panel keeps last state */ }
  try { queue.set(await studioQueue()); } catch { /* panel keeps last state */ }
}
