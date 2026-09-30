/* jarvis-ui · lib/jobs.js — Jobs command center client + live store.
   Polls the tiny local JSON every 5s ONLY while the tab is visible; a click
   writes first, then refreshes at once, so the screen never lags the file. */
import { writable } from "svelte/store";

async function call(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error((await response.text()) || `${path} -> ${response.status}`);
  return response.json();
}

export const jobsOverview = () => call("/api/v1/jobs/overview");
export const jobsBatch = (batch) => call("/api/v1/jobs/batch", { batch });
export const jobsDecide = (batch, n, decision) => call("/api/v1/jobs/decide", { batch, n, decision });
export const jobsAnswer = (batch, n, question, text) =>
  call("/api/v1/jobs/answer", { batch, n, question, text });
export const jobsOpen = (batch, n, which) => call("/api/v1/jobs/open", { batch, n, which });

export const overview = writable(null);
export const detail = writable(null);
export const selected = writable("");
export const notice = writable("");

let current = "";
selected.subscribe((value) => { current = value; });

export async function refresh() {
  try {
    const view = await jobsOverview();
    overview.set(view);
    detail.set(await jobsBatch(current || view.latest));
  } catch (error) {
    notice.set(`Can't reach the jobs data: ${error.message}`);
  }
}

export function live(ms = 5000) {
  refresh();
  const timer = setInterval(() => {
    if (document.visibilityState === "visible") refresh();
  }, ms);
  return () => clearInterval(timer);
}

export async function act(fn, message) {
  try {
    await fn();
    notice.set(message);
  } catch (error) {
    notice.set(error.message);
  }
  await refresh();
}
