<script>
  import { slide } from "svelte/transition";
  import { queue } from "$lib/stores.js";
</script>

<section class="card panel" aria-label="Studio">
  <div class="head"><span class="idx">01 ◆</span>Studio
    <span class="meta">{$queue.armed ? `${$queue.items.length} in queue` : "workflows dark"}</span></div>
  {#each $queue.items as item (item.id)}
    <div class="item" transition:slide={{ duration: 180 }}>
      <div class="t">{item.title || item.id}</div>
      <div class="h">{item.hook || item.source || ""}</div>
      <div class="row terse"><span class="k">score</span>
        <span class="v">{item.score ?? "—"}</span></div>
    </div>
  {:else}
    <div class="row"><span class="k">queue</span>
      <span class="v">{$queue.armed ? "empty — your next draft will land here" : "build the n8n workflows, sir"}</span>
    </div>
  {/each}
</section>

<style>
  .panel { padding: 14px 16px; }
  .head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
    font-size: 11px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; }
  .idx { color: var(--accent-text); }
  .meta { margin-left: auto; color: var(--ink-dim); font-weight: 400; letter-spacing: .12em; }
  .item { border-top: 1px solid var(--line); padding: 8px 0; }
  .item .t { font-size: 12px; }
  .item .h { color: var(--ink-dim); font-size: 11px; margin: 2px 0 6px; }
  .terse { padding-top: 0; }
</style>
