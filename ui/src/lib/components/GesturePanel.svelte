<script>
  import { onMount } from "svelte";
  import { gestureState } from "$lib/api.js";

  let onAir = $state(false);
  let control = $state(false);
  let hands = $state([]);
  let tick = $state(0);

  const W = 100, H = 75;  // 4:3 projection, matches the camera
  const BONES = [
    ["wrist", "thumb_cmc"], ["wrist", "index_mcp"], ["wrist", "middle_mcp"],
    ["wrist", "ring_mcp"], ["wrist", "little_mcp"],
    ["thumb_cmc", "thumb_mp"], ["thumb_mp", "thumb_ip"], ["thumb_ip", "thumb_tip"],
    ["index_mcp", "index_pip"], ["index_pip", "index_dip"], ["index_dip", "index_tip"],
    ["middle_mcp", "middle_pip"], ["middle_pip", "middle_dip"], ["middle_dip", "middle_tip"],
    ["ring_mcp", "ring_pip"], ["ring_pip", "ring_dip"], ["ring_dip", "ring_tip"],
    ["little_mcp", "little_pip"], ["little_pip", "little_dip"], ["little_dip", "little_tip"],
    ["index_mcp", "middle_mcp"], ["middle_mcp", "ring_mcp"], ["ring_mcp", "little_mcp"],
  ];
  const xy = (lm, n) => { const p = lm[n]; return p ? [(1 - p[0]) * W, (1 - p[1]) * H] : null; };
  const skeleton = (lm) => ({
    bones: BONES.map(([a, b]) => [xy(lm, a), xy(lm, b)]).filter(([a, b]) => a && b),
    joints: Object.keys(lm).map((n) => xy(lm, n)).filter(Boolean),
  });
  const drawn = $derived(hands.map((h) => ({ ...h, ...skeleton(h.landmarks) })));

  async function poll() {
    try {
      const s = await gestureState();
      onAir = s.on_air; control = s.control; hands = s.hands || []; tick++;
    } catch { onAir = false; }
  }
  onMount(() => { poll(); const t = setInterval(poll, 55); return () => clearInterval(t); });
</script>


<section class="card focus" aria-label="Gesture control">
  <div class="bar">
    <span class="meta">◆ hand tracking · G3 · point · pinch · swipe · spread</span>
    <span class="onair" class:live={onAir}>{onAir ? "● on air" : "○ off air"}</span>
    <span class="onair" class:live={control}>{control ? "cursor control armed" : "cursor control paused"}</span>
  </div>

  <div class="stage">
    <div class="frame">
      {#if onAir}
        <img class="feed" src="/api/v1/gesture/frame?t={tick}" alt="Live camera" />
      {:else}
        <div class="placeholder"></div>
      {/if}
      <svg viewBox="0 0 {W} {H}" preserveAspectRatio="none" class="overlay"
           role="img" aria-label="Tracked hands">
        {#each drawn as hand, hi (hi)}
          {#each hand.bones as [a, b], i (hi + "b" + i)}
            <line x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} class="bone" />
          {/each}
          {#each hand.joints as j, i (hi + "j" + i)}
            <circle cx={j[0]} cy={j[1]} r="1.2" class="joint" />
          {/each}
        {/each}
      </svg>
      {#if !onAir}
        <div class="hint">Start the gesture agent, allow Camera, and show both hands.</div>
      {/if}
    </div>

    <div class="reads">
      {#each hands as h, i (i)}
        <span class="tag">{h.chirality}: <b>{h.gesture.replace(/_/g, " ")}</b></span>
      {:else}
        {#if onAir}<span class="tag dim">no hands in view</span>{/if}
      {/each}
    </div>
  </div>
</section>

<style>
  .focus { display: flex; flex-direction: column; gap: 14px; padding: 16px 18px 20px; }
  .bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
  .meta { color: var(--ink-dim); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; }
  .onair { font-size: 11px; letter-spacing: .16em; text-transform: uppercase; color: var(--ink-dim); }
  .onair.live { color: var(--accent-text); }
  .stage { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; }
  .frame { position: relative; display: flex; max-width: 92vw; }
  .feed { display: block; max-width: 92vw; max-height: 58vh; transform: scaleX(-1);
    border: 1px solid var(--line); border-radius: 16px; }
  .placeholder { width: min(85vh, 92vw); aspect-ratio: 16 / 9; background: var(--bg);
    border: 1px solid var(--line); border-radius: 16px; }
  .overlay { position: absolute; inset: 0; width: 100%; height: 100%; }
  .bone { stroke: var(--accent-text); stroke-width: 0.7; stroke-linecap: round; opacity: .9; }
  .joint { fill: var(--ink); }
  .hint { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
    text-align: center; color: var(--ink-dim); font-size: 12px; padding: 0 16px; }
  .reads { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; min-height: 20px; }
  .tag { font-size: 12px; letter-spacing: .06em; text-transform: uppercase; color: var(--ink-dim); }
  .tag b { color: var(--ink); }
  .tag.dim { opacity: .6; }
</style>
