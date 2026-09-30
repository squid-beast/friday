<script>
  /* Dashboard glance: tonight's batch + pipeline. Read-only (the cockpit stays
     button-free); the full command center lives at /jobs. */
  import { onMount } from "svelte";
  import { jobsOverview } from "$lib/jobs.js";

  let view = $state(null);
  onMount(() => {
    const load = () => jobsOverview().then((v) => { view = v; }).catch(() => {});
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  });
  const s = $derived(view?.summary ?? {});
  const pipe = $derived(view?.pipeline?.by_status ?? {});
</script>

<section class="card panel" aria-label="Jobs">
  <div class="head"><span class="idx">07 ◆</span>Jobs
    <span class="meta">{view?.latest ? `batch ${view.latest}` : "no batch yet"}</span></div>
  <div class="row"><span class="k">ready</span><span class="v">{s.total ?? 0} roles</span></div>
  <div class="row"><span class="k">needs you</span><span class="v">{s.needs_you ?? 0}</span></div>
  <div class="row"><span class="k">approved</span><span class="v">{s.approved ?? 0} · skipped {s.skipped ?? 0}</span></div>
  <div class="row"><span class="k">pipeline</span>
    <span class="v">{pipe.applied ?? 0} applied · {pipe.rejected ?? 0} rejected · {pipe.interview ?? 0} interviews</span></div>
  <a class="open" href="/jobs">Open the command center →</a>
</section>

<style>
  .panel { padding: 14px 16px; }
  .head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; }
  .idx { color: var(--accent-text); }
  .meta { margin-left: auto; color: var(--ink-dim); font-weight: 400; letter-spacing: .12em; }
  .open { display: inline-flex; align-items: center; min-height: 44px; margin-top: 6px;
    color: var(--accent-text); font-size: 12px; letter-spacing: .08em; }
</style>
