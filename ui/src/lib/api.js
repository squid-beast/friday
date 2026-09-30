/* friday-ui · lib/api.js — the ONE place the UI talks HTTP. Versioned,
   meaningful endpoints; auth rides the gate cookie set at first visit. */

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return response.json();
}

/** Armed systems, queue depth, next event, recent activity. */
export const systemStatus = () => request("/api/v1/system/status");

/** 14-day metric series per platform (the sparkline cards). */
export const metrics = () => request("/api/v1/metrics");

/** Today's calendar + Friday activity log. */
export const agenda = () => request("/api/v1/agenda");

/** The last few spoken turns (Mac voice or phone), newest thread. */
export const recentConversation = () => request("/api/v1/conversation/recent");

/** Content Studio review queue (panel parked). -> {items, armed} */
export const studioQueue = () => request("/api/v1/studio/queue");

export const visionSnaps = () => request("/api/v1/vision/snaps");

export const gestureState = () => request("/api/v1/gesture/state");

/** The HUD's single glance payload: system, weather, reminders, automations. */
export const hud = () => request("/api/v1/hud");
