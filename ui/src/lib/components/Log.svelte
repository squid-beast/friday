<script>
  /* The last spoken turns, straight from the brain's checkpoint store — voice
     from the Mac or text from the phone. Read-only, polled; no input here. */
  import { onMount } from "svelte";
  import { fly } from "svelte/transition";
  import { recentConversation } from "$lib/api.js";

  let view = $state([]);

  async function pull() {
    try { view = (await recentConversation()).messages ?? []; } catch { /* keep last */ }
  }

  onMount(() => {
    pull();
    const timer = setInterval(pull, 10000);
    return () => clearInterval(timer);
  });
</script>

<main aria-live="polite" aria-label="Conversation log">
  {#each view as m, i (i)}
    <div class="msg {m.who}"
         transition:fly={{ y: 14, duration: 220 }}>
      {m.text}
    </div>
  {:else}
    <div class="empty">Friday will show your most recent spoken turns here.</div>
  {/each}
</main>

<style>
  main { min-height: 0; display: flex; flex-direction: column; gap: 10px; }
  .empty { border: 1px dashed var(--line); border-radius: 16px; background: var(--bg);
    padding: 18px; color: var(--ink-dim); }
  .msg { position: relative; max-width: 88%; padding: 12px 14px;
    border: 1px solid var(--line); border-radius: 16px;
    background: var(--surface); white-space: pre-wrap; }
  .me { align-self: flex-end; border-right: 2px solid var(--accent); }
  .friday { align-self: flex-start; }
  .friday::before { content: "◆ friday"; display: block; font-size: 9px;
    letter-spacing: .25em; text-transform: uppercase; color: var(--ink-dim);
    margin-bottom: 4px; }
</style>
