<script>
  /* Jobs command center: tonight's batch, live. Clicks write straight to the
     Mac's decisions file, which the next Claude run reads. */
  import { onMount } from "svelte";
  import JobRow from "$lib/components/jobs/JobRow.svelte";
  import { detail, live, notice, overview, refresh, selected } from "$lib/jobs.js";

  let filter = $state("all");
  onMount(() => live(5000));

  const roles = $derived($detail?.roles ?? []);
  const shown = $derived(roles.filter((r) =>
    filter === "all" ? true
      : filter === "needs" ? (r.needs ?? []).length > 0
        : filter === "undecided" ? !r.decision
          : r.submit_mode === filter));
  const s = $derived($detail?.summary ?? {});
  const pipe = $derived($overview?.pipeline ?? { by_status: {}, recent: [] });
  const prog = $derived($detail?.progress ?? {});
  const pick = (b) => { selected.set(b); refresh(); };
</script>

<svelte:head><title>Friday · Jobs</title></svelte:head>

<section class="jobs" aria-label="Jobs command center">
  <div class="bar">
    <a class="back" href="/">← Dashboard</a>
    <h2>Jobs · {$detail?.batch ?? "…"}</h2>
    <label class="pick">Batch
      <select value={$detail?.batch ?? ""} onchange={(e) => pick(e.currentTarget.value)}>
        {#each $overview?.batches ?? [] as b (b)}<option value={b}>{b}</option>{/each}
      </select>
    </label>
  </div>

  <div class="stats">
    <div class="card stat"><span class="k">Roles</span><b>{s.total ?? 0}</b>
      <span class="sub">{Object.entries(s.by_tier ?? {}).map(([k, v]) => `${k} ${v}`).join(" · ")}</span></div>
    <div class="card stat"><span class="k">Decided</span><b>{(s.approved ?? 0) + (s.skipped ?? 0)}</b>
      <span class="sub">{s.approved ?? 0} approved · {s.skipped ?? 0} skipped · {s.undecided ?? 0} left</span></div>
    <div class="card stat"><span class="k">Needs you</span><b>{s.needs_you ?? 0}</b>
      <span class="sub">{$overview?.code_queue ?? 0} in the 11 AM code queue</span></div>
    <div class="card stat"><span class="k">Pipeline</span><b>{pipe.total ?? 0}</b>
      <span class="sub">{Object.entries(pipe.by_status ?? {}).map(([k, v]) => `${v} ${k}`).join(" · ")}</span></div>
    <div class="card stat"><span class="k">Tonight's run</span>
      <b>{prog.done?.length ? prog.done.at(-1) : "—"}</b>
      <span class="sub">{prog.updated ? `updated ${prog.updated}` : "no run in progress"}</span></div>
  </div>

  {#if $notice}<p class="notice" aria-live="polite">{$notice}</p>{/if}

  <div class="card list">
    <div class="filters" role="group" aria-label="Filter roles">
      {#each [["all", "All"], ["needs", "Needs you"], ["undecided", "Undecided"], ["claude", "Claude submits"], ["portal", "Portals"], ["leo", "Yours"]] as [key, label] (key)}
        <button class="ghost" class:live={filter === key} onclick={() => { filter = key; }}>{label}</button>
      {/each}
    </div>
    {#each shown as role (role.n)}
      <JobRow {role} batch={$detail.batch} />
    {:else}
      <p class="empty">Nothing here for this filter.</p>
    {/each}
  </div>
</section>

<style>
  .jobs { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 18px 24px; display: grid; gap: 14px; align-content: start; }
  .bar { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
  .back { color: var(--accent-text); min-height: 44px; display: inline-flex; align-items: center; }
  h2 { font-size: clamp(20px, 2.4vw, 30px); letter-spacing: -.02em; flex: 1; }
  .pick { display: flex; gap: 8px; align-items: center; font-size: 12px; color: var(--ink-dim); }
  select { font: inherit; min-height: 44px; border: 1px solid var(--line); border-radius: 12px;
    background: var(--surface); color: var(--ink); padding: 0 10px; }
  .stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
  .stat { padding: 12px 14px; display: grid; gap: 2px; }
  .stat .k { color: var(--ink-dim); font-size: 10px; letter-spacing: .24em; text-transform: uppercase; }
  .stat b { font-size: 26px; }
  .sub { color: var(--ink-dim); font-size: 11px; }
  .notice { color: var(--accent-text); font-size: 12px; }
  .list { padding: 8px 16px 12px; }
  .filters { display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 0 12px; }
  .empty { color: var(--ink-dim); padding: 12px 0; }
</style>
