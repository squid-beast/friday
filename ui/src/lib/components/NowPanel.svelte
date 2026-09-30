<script>
  import { status } from "$lib/stores.js";

  const rows = $derived(
    [["next event", $status.next_event || "none today"]].concat(
      $status.activity.length
        ? $status.activity.map((a) => [a.ts, a.label ?? a.kind])
        : [["activity", "quiet so far"]],
    ),
  );
</script>

<section class="card panel" aria-label="Now">
  <div class="head"><span class="idx">00 ◆</span>Now
    <span class="meta">{$status.queue ? `${$status.queue} queued` : "clear"}</span></div>
  {#each rows as [k, v] (k + v)}
    <div class="row"><span class="k">{k}</span><span class="v">{v}</span></div>
  {/each}
</section>

<style>
  .panel { padding: 14px 16px; }
  .head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; }
  .idx { color: var(--accent-text); }
  .meta { margin-left: auto; color: var(--ink-dim); font-weight: 400; letter-spacing: .12em; }
</style>
