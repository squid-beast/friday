# Friday makes phone calls (what to set up)

Friday can dial a real number and speak to a person **on your behalf**. It's the
highest-risk tool in the system, so it's **PIN-gated** (spoken 4-digit PIN) and
refuses until you configure a provider. The adapter is `adapters/telephony.py`;
it's inert until the `.env` values below are set — nothing half-working runs.

## What it needs (three things)
1. A **phone number** the calls originate from.
2. A **telephony provider** that bridges an AI voice to real phone lines.
3. **Consent** — in most places an AI call must announce itself; keep the
   assistant's opening line honest ("Hello, I'm an assistant calling on behalf of
   Lohith…"). This is on you, not the code.

## Fastest path — Vapi (turnkey, recommended)
1. Sign up at **vapi.ai**. Cost ~$0.05–0.15/min.
2. Create an **Assistant** — give it Friday's manner and the calling goal
   (reschedule, ask a question, etc.). Note its **assistant id**.
3. Buy/import a **phone number** in Vapi. Note its **phone number id**.
4. Grab your **API key**.
5. Put in `.env`:
   ```
   TELEPHONY_PROVIDER=vapi
   TELEPHONY_API_KEY=<your vapi key>
   TELEPHONY_FROM_NUMBER=<phone number id>
   TELEPHONY_AGENT_ID=<assistant id>
   ```
6. Restart the app/voice worker. Before the first real call, confirm the endpoint
   and body in `adapters/telephony.py` (`_VAPI_URL`, `_place_vapi`) against Vapi's
   current API docs — they're written to their documented shape but verify once.

## Alternative — Twilio + our LiveKit (DIY, cheapest/min, most setup)
Buy a Twilio number (~$1/mo), set up a SIP trunk into the LiveKit we already run,
and bridge the voice agent over SIP. More control, more wiring — the
`telephony_provider != "vapi"` branch is the seam; say the word and I'll build it.

## Using it
Say (or type): **"call +1 415-555-2671 and reschedule my appointment."** Friday
extracts the number, asks for your **PIN**, and on the correct code places the
call with your goal as context. No number in the request → it asks for one.
