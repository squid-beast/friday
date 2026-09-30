<script>
  import { onMount } from "svelte";
  import { metrics } from "$lib/api.js";

  let data = $state({});

  onMount(async () => {
    try { data = await metrics(); } catch { data = {}; }
  });

  const rows = $derived(
    Object.entries(data).flatMap(([platform, series]) =>
      Object.entries(series).map(([metric, points]) => {
        const max = Math.max(...points.map((p) => p.value), 1);
        return {
          key: `${platform} · ${metric.replaceAll("_", " ")}`,
          latest: points[points.length - 1].value,
          bars: points.slice(-18).map((p) => Math.max(8, Math.round((p.value / max) * 100))),
        };
      }),
    ),
  );
</script>

<section class="card panel" aria-label="Metrics">
  <div class="head"><span class="idx">02 ◆</span>Metrics
    <span class="meta">14d</span></div>
  {#each rows as r (r.key)}
    <div class="row"><span class="k">{r.key}</span>
      <span class="spark" aria-hidden="true">
        {#each r.bars as h, i (i)}<i style:height="{h}%"></i>{/each}
      </span>
      <span class="v">{Number(r.latest.toFixed(2)).toLocaleString()}</span>
    </div>
  {:else}
    <div class="row"><span class="k">no signals yet</span>
      <span class="v">run make collect, sir</span></div>
  {/each}
</section>

<style>
  .panel { padding: 14px 16px; }
  .head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; }
  .idx { color: var(--accent-text); }
  .meta { margin-left: auto; color: var(--ink-dim); font-weight: 400; letter-spacing: .12em; }
</style>
