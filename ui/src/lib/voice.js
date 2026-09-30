/* jarvis-ui · lib/voice.js — one voice session for the whole app: connect from
   the cockpit composer or the /voice orbit, same room, same rules. STAND DOWN
   always fires the brain's REAL kill path (audited) before hanging up.
   livekit-client loads lazily: it stays out of the boot bundle and away from
   the prerenderer (WebRTC is a browser-only world). */
import { writable } from "svelte/store";
import { converse, voiceSession } from "$lib/api.js";

export const vox = writable({ live: false, state: "voice dormant" });
let room = null;

export async function voiceConnect() {
  vox.set({ live: false, state: "dialing the house" });
  try {
    const [{ url, token }, livekit] = await Promise.all([
      voiceSession(),
      import("livekit-client"),
    ]);
    const { Room, RoomEvent, createLocalAudioTrack } = livekit;
    room = new Room();
    room.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === "audio") track.attach();
    });
    room.on(RoomEvent.Disconnected, () => {
      room = null;
      vox.set({ live: false, state: "voice dormant" });
    });
    await room.connect(url, token);
    await room.startAudio();
    const mic = await createLocalAudioTrack({
      echoCancellation: true, noiseSuppression: true,
    });
    await room.localParticipant.publishTrack(mic);
    vox.set({ live: true, state: "live · at your service" });
  } catch (error) {
    room = null;
    vox.set({
      live: false,
      state: String(error).includes("400")
        ? "voice not configured — docs/PHONE.md" : "can't reach the house",
    });
  }
}

export function standDown() {
  converse("stand down").catch(() => {});
  if (room) room.disconnect();
}

export const voiceToggle = () => (room ? standDown() : voiceConnect());
