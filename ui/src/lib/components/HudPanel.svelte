<script>
  import { onMount } from "svelte";
  import { fade, fly } from "svelte/transition";
  import { hud, visionSnaps } from "$lib/api.js";

  let data = $state(null);
  let now = $state(new Date(0));
  let snaps = $state([]);

  const two = (n) => String(n).padStart(2, "0");
  const clock = $derived(`${two(now.getHours())}:${two(now.getMinutes())}:${two(now.getSeconds())}`);
  const date = $derived(now.getTime()
    ? now.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }) : "");

  async function refresh() {
    try { data = await hud(); } catch { /* keep last */ }
    try { snaps = (await visionSnaps()).snaps ?? []; } catch { /* keep last */ }
  }

  onMount(() => {
    refresh();
    now = new Date();
    const tick = setInterval(() => (now = new Date()), 1000);
    const pull = setInterval(refresh, 6000);
    return () => { clearInterval(tick); clearInterval(pull); };
  });

  const w = $derived(data?.weather ?? {});
  const sys = $derived(data?.system ?? { cpu: 0, ram: 0, disk: 0, uptime_h: 0 });
  const rem = $derived(data?.reminders ?? { items: [], notes: [] });
  const autos = $derived(data?.automations ?? { runs: [], counts: {}, armed: false });
  const daemon = $derived(data?.daemon ?? "off");
</script>


<section class="hud" aria-label="HUD">
  <aside class="left">
    <div class="card time">
      <div class="big">{clock}</div>
      <div class="sub">{date}</div>
      <div class="state {daemon}">{daemon === "active" ? "● listening" :
        daemon === "dormant" ? "○ resting — use the wake phrase above" : "— daemon off"}</div>
    </div>

    <div class="card">
      <h2><span class="idx">◆</span>Weather</h2>
      {#if w.temp !== undefined}
        <div class="wrow"><span class="temp">{w.temp}°F</span>
          <span class="cond">{w.city}<br>{w.condition}</span></div>
        <div class="row"><span class="k">feels like</span><span class="v">{w.feels}°F</span></div>
        <div class="row"><span class="k">high / low</span><span class="v">{w.high}° / {w.low}°</span></div>
        <div class="row"><span class="k">chance of rain</span><span class="v">{w.rain}%</span></div>
        <div class="row"><span class="k">wind · humidity</span><span class="v">{w.wind} mph · {w.humidity}%</span></div>
      {:else}<div class="sub">set WEATHER_CITY, sir</div>{/if}
    </div>

    <div class="card">
      <h2><span class="idx">◆</span>System</h2>
      <div class="meter"><span class="k">CPU</span>
        <span class="bar"><i style:width="{sys.cpu}%"></i></span><span class="v">{sys.cpu}%</span></div>
      <div class="meter"><span class="k">Memory</span>
        <span class="bar"><i style:width="{sys.ram}%"></i></span><span class="v">{sys.ram}%</span></div>
      <div class="meter"><span class="k">Disk</span>
        <span class="bar"><i style:width="{sys.disk}%"></i></span><span class="v">{sys.disk}%</span></div>
      <div class="row"><span class="k">running for</span><span class="v">{sys.uptime_h}h</span></div>
    </div>
  </aside>

  <div class="main">
    <div class="card">
      <h2><span class="idx">◆</span>Snaps
        <span class="counts">{snaps.length ? `${snaps.length} seen` : ""}</span></h2>
      {#if snaps.length}
        <div class="snaps">
          {#each snaps.slice(0, 8) as id (id)}
            <div class="snap" in:fade={{ duration: 160 }}>
              <img src="/api/v1/vision/snaps/{id}" alt="what Friday saw at {id}" loading="lazy" />
              <span class="stamp">{id.slice(9, 11)}:{id.slice(11, 13)}</span>
            </div>
          {/each}
        </div>
      {:else}
        <div class="sub">{data?.eyes
          ? "no snaps yet — say \"what am I holding?\" and I’ll show you what I see"
          : "vision offline — no model is listening, so Friday won't take snaps"}</div>
      {/if}
    </div>

    <div class="card">
      <h2><span class="idx">◆</span>Notes &amp; Reminders</h2>
      {#each rem.items as item (item.text)}
        <div class="row" in:fly={{ y: 8, duration: 160 }}>
          <span class="k">{item.source === "you" ? "reminder" : item.source}</span>
          <span class="v note">{item.text}</span></div>
      {:else}<div class="sub">nothing pending — say "remind me to ..."</div>{/each}
      <div class="notes">
        <span class="k">Obsidian memory</span>
        <div class="sub">Friday can answer from your notes without copying them out of Obsidian.</div>
        <div class="sub">Say "open my notes" to open Obsidian itself.</div>
        {#if rem.notes.length}
          <div class="chips">{#each rem.notes as n (n)}
            <span class="chip note-chip">{n}</span>{/each}</div>
        {/if}
      </div>
    </div>

    <div class="card">
      <h2><span class="idx">◆</span>Automations
        <span class="counts">{#each Object.entries(autos.counts) as [st, c] (st)}
          <span class="chip {st}">{c} {st}</span>{/each}</span>
      </h2>
      {#if autos.runs.length}
        {#each autos.runs.slice(0, 5) as run (run.id)}
          <div class="run {run.status}">
            <span class="dot {run.status}"></span>
            <span class="name">{run.name}</span>
            <span class="v">{run.status} · {run.when}{run.today > 1 ? ` · ${run.today}× today` : ""}</span>
          </div>
        {/each}
      {:else}
        <div class="sub">{autos.error ? autos.error
          : autos.armed ? "no workflow runs yet" : "n8n not configured"}</div>
      {/if}
    </div>
  </div>
</section>

<style>
  .hud { display: flex; gap: 12px; align-items: flex-start; }
  .left { display: flex; flex-direction: column; gap: 12px; width: 300px; flex-shrink: 0; }
  .main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12px; }
  .card { border: 1px solid var(--line); border-radius: 16px; background: var(--surface); padding: 16px 18px; }
  h2 { font-size: 11px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase;
    margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
  h2 .idx { color: var(--accent-text); }
  .big { font-size: 30px; font-weight: 700; font-variant-numeric: tabular-nums;
    letter-spacing: .04em; }
  .sub { color: var(--ink-dim); font-size: 12px; margin-top: 2px;
    letter-spacing: .06em; text-transform: uppercase; }
  .time .state { margin-top: 10px; font-size: 11px; letter-spacing: .16em;
    text-transform: uppercase; color: var(--ink-dim); }
  .time .state.active { color: var(--accent-text); }
  .wrow { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
  .wrow .temp { font-size: 30px; font-weight: 700; }
  .wrow .cond { color: var(--ink-dim); font-size: 11px; text-transform: uppercase;
    letter-spacing: .08em; line-height: 1.5; }
  .row { display: flex; justify-content: space-between; gap: 10px; padding: 6px 0;
    border-top: 1px solid var(--line); font-size: 12px; }
  .row .k { color: var(--ink-dim); text-transform: uppercase; letter-spacing: .06em; }
  .row .v { text-align: right; }
  .row .v.note { text-transform: none; letter-spacing: 0; }
  .meter { display: grid; grid-template-columns: 64px 1fr 42px; gap: 8px;
    align-items: center; padding: 6px 0; }
  .meter .k { color: var(--ink-dim); font-size: 11px; text-transform: uppercase; }
  .meter .v { text-align: right; font-variant-numeric: tabular-nums; }
  .bar { height: 8px; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; }
  .bar i { display: block; height: 100%; background: var(--accent); transition: width .5s; }
  .notes { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--line); }
  .notes .k { color: var(--ink-dim); font-size: 11px; text-transform: uppercase;
    letter-spacing: .06em; }
  .note-chip { min-height: 32px; display: inline-flex; align-items: center; font-family: inherit; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
  .chip { border: 1px solid var(--line); border-radius: 999px; background: var(--bg);
    color: var(--ink-dim); font-size: 10px; letter-spacing: .06em; padding: 2px 8px; }
  .chip.success { color: var(--ink); } .chip.error { color: var(--accent-text); }
  .counts { margin-left: auto; display: flex; gap: 6px; }
  .run { display: flex; align-items: center; gap: 10px; padding: 8px 0;
    border-top: 1px solid var(--line); font-size: 12px; }
  .run .name { flex: 1; }
  .run .v { color: var(--ink-dim); text-transform: uppercase; letter-spacing: .06em; }
  .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ink-dim); }
  .dot.success { background: var(--ink); } .dot.error { background: var(--accent); }
  .dot.running { background: var(--accent-text); }
  .snaps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .snap { position: relative; display: block; border: 1px solid var(--line);
    border-radius: 14px; overflow: hidden; aspect-ratio: 4 / 3; background: var(--bg); }
  .snap img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .snap .stamp { position: absolute; bottom: 0; right: 0; font-size: 10px;
    font-variant-numeric: tabular-nums; letter-spacing: .06em; padding: 1px 5px;
    background: var(--surface); color: var(--ink-dim); border-top-left-radius: 10px; }
  @media (max-width: 720px) {
    .hud { flex-direction: column; }
    .snaps { grid-template-columns: repeat(3, 1fr); }
    .left { width: 100%; flex-direction: row; flex-wrap: wrap; }
    .left .card { flex: 1; min-width: 150px; }
  }
</style>
