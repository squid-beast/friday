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

const post = (path, body) =>
  request(path, { method: "POST", body: JSON.stringify(body ?? {}) });

/** Speak to the brain. -> {reply, pending} */
export const converse = (text) => post("/api/v1/conversation", { text });

/** Armed systems, queue depth, next event, recent activity. */
export const systemStatus = () => request("/api/v1/system/status");

/** 14-day metric series per platform (the sparkline cards). */
export const metrics = () => request("/api/v1/metrics");

/** Today's calendar + Friday activity log. */
export const agenda = () => request("/api/v1/agenda");

/** Content Studio review queue. -> {items, armed} */
export const studioQueue = () => request("/api/v1/studio/queue");
export const studioRefresh = () => post("/api/v1/studio/queue/refresh");
export const studioPublish = (id, caption = "") =>
  post("/api/v1/studio/publish", { id, caption });
export const studioSkip = (id) => post("/api/v1/studio/skip", { id });

/** LiveKit credentials for the voice room. -> {url, token, room} */
export const voiceSession = () => request("/api/v1/voice/session");

export const visionSnaps = () => request("/api/v1/vision/snaps");

export const gestureState = () => request("/api/v1/gesture/state");

/** The HUD's single glance payload: system, weather, reminders, automations. */
export const hud = () => request("/api/v1/hud");
