<script>
  import HudPanel from "$lib/components/HudPanel.svelte";
  import JobsPanel from "$lib/components/JobsPanel.svelte";
  import Log from "$lib/components/Log.svelte";
  import MetricsPanel from "$lib/components/MetricsPanel.svelte";
  import NowPanel from "$lib/components/NowPanel.svelte";
  import TodayPanel from "$lib/components/TodayPanel.svelte";
  import { status } from "$lib/stores.js";

  const identity = $derived($status.identity ?? { wake_phrase_active: "Hey Jarvis" });
</script>

<svelte:head><title>Friday</title></svelte:head>

<section class="dash" aria-label="Friday dashboard">
  <div class="hero">
    <div class="intro card">
      <div class="eyebrow">Friday Command Center</div>
      <h2>Everything important, one glance.</h2>
      <p>Say <b>{identity.wake_phrase_active}</b> to wake the house. Say <b>Stand Down</b> when you want silence.</p>
    </div>
    <div class="conversation card">
      <div class="eyebrow">Recent conversation</div>
      <Log />
    </div>
  </div>

  <div class="grid">
    <NowPanel />
    <MetricsPanel />
    <TodayPanel />
    <JobsPanel />
    <div class="wide"><HudPanel /></div>
  </div>
</section>

<style>
  .dash { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 18px 20px; display: grid; gap: 14px; }
  .hero { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(380px, 1.3fr); gap: 14px; }
  .intro { padding: 18px; display: grid; gap: 10px; }
  .eyebrow { color: var(--ink-dim); font-size: 10px; letter-spacing: .24em; text-transform: uppercase; }
  h2 { font-size: clamp(24px, 3vw, 40px); line-height: 1.05; letter-spacing: -.03em; }
  p { color: var(--ink-dim); max-width: 46ch; }
  .conversation { padding: 14px 16px; display: grid; gap: 8px; min-height: 220px; }
  .grid { display: grid; align-content: start; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
  .wide { grid-column: 1 / -1; }
  @media (max-width: 900px) {
    .hero { grid-template-columns: 1fr; }
  }
</style>
