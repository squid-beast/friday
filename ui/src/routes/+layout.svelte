<script>
  import "../app.css";
  import { onMount } from "svelte";
  import { refreshPanels, status } from "$lib/stores.js";

  let { children } = $props();
  const mac = $derived($status.daemon);
  const identity = $derived($status.identity ?? {
    assistant: "Friday",
    wake_phrase: "Hey Friday",
    wake_phrase_active: "Hey Jarvis",
    wake_phrase_ready: false,
    stand_down_phrase: "Stand Down",
    voice_lock: "open",
    voice_lock_ready: false,
    voice_lock_scope: "wake-only",
  });

  onMount(() => {
    refreshPanels();
    const timer = setInterval(refreshPanels, 60000);
    return () => clearInterval(timer);
  });
</script>

<div id="frame">
  <header>
    <div class="brand">
      <div class="eyebrow">Voice-first life OS</div>
      <h1>{identity.assistant}</h1>
    </div>
    <div class="ruler" aria-hidden="true"></div>
    <div class="signals" aria-label="Friday status">
      <span class="signal" class:live={mac === "active"}>
        {mac === "active" ? "● Listening now"
          : mac === "dormant" ? "○ Resting" : "— Daemon off"}
      </span>
      <span class="signal" class:live={identity.wake_phrase_ready}>{identity.wake_phrase_active}</span>
      <span class="signal">{identity.stand_down_phrase}</span>
      <span class="signal" class:live={identity.voice_lock_ready}>
        {identity.voice_lock_ready
          ? "Voice lock armed"
          : identity.voice_lock === "strict"
            ? "Voice lock needs your samples"
            : "Voice lock open"}
      </span>
      <span class="signal">{identity.voice_lock_scope}</span>
    </div>
  </header>

  {@render children()}
</div>

<style>
  #frame { height: 100dvh; display: flex; flex-direction: column; overflow: hidden; }
  header {
    padding: max(14px, env(safe-area-inset-top)) 18px 14px;
    border-bottom: 1px solid var(--line);
    display: grid; grid-template-columns: auto 1fr auto; gap: 16px; align-items: center;
  }
  .brand { display: grid; gap: 3px; }
  .eyebrow { color: var(--ink-dim); font-size: 10px; letter-spacing: .22em; text-transform: uppercase; }
  .signals { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
  .signal {
    border: 1px solid var(--line);
    border-radius: 999px;
    background: var(--surface);
    color: var(--ink-dim);
    font-size: 10px;
    letter-spacing: .16em;
    text-transform: uppercase;
    padding: 7px 10px;
    white-space: nowrap;
  }
  .signal.live { color: var(--accent-text); border-color: var(--accent); }
  @media (max-width: 860px) {
    header { grid-template-columns: 1fr; }
    .signals { justify-content: flex-start; }
  }
</style>
