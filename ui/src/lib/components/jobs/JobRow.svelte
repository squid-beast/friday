<script>
  /* One role: decide, answer what it needs, open its files on the Mac. */
  import { act, jobsAnswer, jobsDecide, jobsOpen } from "$lib/jobs.js";

  let { role, batch } = $props();
  let drafts = $state({});
  const who = $derived(role.submit_mode === "leo" ? "You submit"
    : role.submit_mode === "portal" ? "Portal · sign in" : "Claude submits");
  const decide = (d) => act(() => jobsDecide(batch, role.n, d),
    d ? `#${role.n} ${role.company}: ${d}d` : `#${role.n} cleared`);
  const save = (q) => act(() => jobsAnswer(batch, role.n, q, drafts[q] ?? role.answers[q] ?? ""),
    `#${role.n}: answer saved`);
  const open = (which) => act(() => jobsOpen(batch, role.n, which), `Opening ${which} for #${role.n}`);
</script>

<article class="job" class:approved={role.decision === "approve"} class:skipped={role.decision === "skip"}
  aria-label={`#${role.n} ${role.company} ${role.role}`}>
  <div class="top">
    <span class="n">#{role.n}</span>
    <div class="what">
      <div class="co">{role.company} <span class="chip">{role.tier}</span> <span class="chip">{who}</span></div>
      <a class="title" href={role.url} target="_blank" rel="noopener noreferrer">{role.role}</a>
    </div>
    <div class="state" aria-live="polite">{role.decision || "undecided"}</div>
  </div>

  <div class="actions">
    <button onclick={() => decide("approve")} disabled={role.decision === "approve"}
      aria-label={`Approve #${role.n}`}>Approve</button>
    <button class="ghost" onclick={() => decide("skip")} disabled={role.decision === "skip"}
      aria-label={`Skip #${role.n}`}>Skip</button>
    {#if role.decision}
      <button class="ghost" onclick={() => decide("")} aria-label={`Clear #${role.n}`}>Undo</button>
    {/if}
    <button class="ghost" onclick={() => open("resume")} disabled={!role.files.resume}>Resume</button>
    <button class="ghost" onclick={() => open("cover")} disabled={!role.files.cover}>Letter</button>
    <button class="ghost" onclick={() => open("folder")} disabled={!role.files.folder}>Folder</button>
  </div>

  {#each role.needs ?? [] as q (q)}
    <label class="need">
      <span class="q">{q}</span>
      <span class="line">
        <input value={role.answers[q] ?? ""} placeholder="Your answer"
          oninput={(e) => { drafts[q] = e.currentTarget.value; }} aria-label={`Answer for #${role.n}: ${q}`} />
        <button class="ghost" onclick={() => save(q)}>Save</button>
      </span>
    </label>
  {/each}
  {#each role.consents ?? [] as c (c)}
    <div class="consent">Consent on this form: {c}</div>
  {/each}
</article>

<style>
  .job { border-top: 1px solid var(--line); padding: 12px 0; display: grid; gap: 8px; }
  .job.approved { border-left: 3px solid var(--accent); padding-left: 10px; }
  .job.skipped { opacity: .55; }
  .top { display: flex; gap: 10px; align-items: baseline; }
  .n { color: var(--ink-dim); font-size: 12px; min-width: 32px; }
  .what { flex: 1; min-width: 0; }
  .co { font-weight: 700; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .title { color: var(--accent-text); font-size: 12px; }
  .state { color: var(--ink-dim); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; }
  .need { display: grid; gap: 4px; font-size: 12px; }
  .q { color: var(--ink-dim); }
  .line { display: flex; gap: 8px; }
  .consent { font-size: 11px; color: var(--ink-dim); }
</style>
