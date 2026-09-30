<script>
  /* The day at full width: calendar (honest permission hint) + activity log. */
  import { onMount } from "svelte";
  import { agenda } from "$lib/api.js";
  let day = $state({ calendar: [], activity: [] });
  async function pull() { try { day = await agenda(); } catch { /* keep last */ } }
  onMount(() => {
    pull();
    const timer = setInterval(pull, 60000);
    return () => clearInterval(timer);
  });
</script>


<section class="focus" aria-label="Today">
  <div class="card block">
    <h2><span class="idx">00 ◆</span>Calendar</h2>
    {#if day.calendar === null}
      <div class="row"><span class="k">access</span>
        <span class="v">grant Calendar permission, sir (make collect)</span></div>
    {:else}
      {#each day.calendar as line (line)}
        <div class="row"><span class="v">{line}</span></div>
      {:else}
        <div class="row"><span class="k">events</span>
          <span class="v">nothing on the books today</span></div>
      {/each}
    {/if}
  </div>
  <div class="card block">
    <h2><span class="idx">01 ◆</span>Activity</h2>
    {#each day.activity.slice().reverse() as entry, i (i)}
      <div class="row"><span class="k">{entry.ts}</span>
        <span class="v note">{entry.label ?? entry.kind}</span></div>
    {:else}
      <div class="row"><span class="k">log</span>
        <span class="v">quiet so far, sir</span></div>
    {/each}
  </div>
</section>

<style>
  .focus { flex: 1; min-height: 0; overflow-y: auto; padding: 10px 16px;
    display: flex; flex-direction: column; gap: 10px; }
  .block { padding: 12px 14px; }
  h2 { font-size: 11px; font-weight: 700; letter-spacing: .3em;
    text-transform: uppercase; margin-bottom: 8px; }
  h2 .idx { color: var(--accent-text); }
  .row .v.note { text-transform: none; letter-spacing: 0; }
</style>
