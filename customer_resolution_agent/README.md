# Customer-Facing Resolution Agent — Airline Disruption

Interview-ready prototype for Assignment 3. It demonstrates a reliable, auditable support agent that understands customer intent, applies only the supplied policy, records authorized actions, and escalates when authority is missing.

## Reviewer demo
- **Priya:** cancelled SK-204 — refund/rebooking choice, Gold priority rebooking, unsupported free business upgrade.
- **Arvind:** 4-hour delay — meal + lounge eligibility; hotel rejected.
- **Meher:** 6-hour delay — delayed-hours hotel; full-night request rejected; ₹2,000 fare-waiver escalated above the ₹1,500 authority limit.
- Legal/formal complaint language escalates immediately.
- Refund to another payment method is blocked.
- Missing fare-difference amount triggers one necessary follow-up.
- Every message, decision, action, and escalation is timestamped.

## Architecture
```text
Streamlit UI
   -> intent extraction
   -> deterministic policy / authority engine
      -> allowed: simulated action record
      -> missing fact: ask only for that fact
      -> outside authority: escalate
   -> conversation + audit trail
```

### Why deterministic instead of an external LLM?
The exercise supplies a tiny fixed policy/data set and says not to invent rules or customer information. A deterministic policy engine is testable, auditable, needs no API key, and avoids hallucinated airline rules. In production, an LLM could improve language understanding while this policy/authority layer remains deterministic.

## Structure
```text
app.py              Streamlit UI/session/audit state
agent.py            intent + policy + authority engine
data.py             supplied customer/booking/policy data
tests/test_agent.py automated decision tests
requirements.txt
README.md
```

## Run
Python 3.10+ recommended.
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Test
```bash
pytest -q
```

## Important design decisions
1. Source-grounded: no external airline facts.
2. Multi-intent: one message can contain an allowed and unsupported request.
3. No false integration claims: actions are simulated because no live airline APIs were supplied.
4. Minimal questions: known booking data is reused; missing decision-critical information is requested.
5. Policy gaps are not guessed.
6. Auditability: structured actions are separate from conversational text.

## Requirement coverage
| Requirement | Implementation |
|---|---|
| Understand intent | Multi-intent extraction in `agent.py` |
| Ask only necessary questions | Reuses supplied data; asks only for missing fare amount when required |
| Use supplied data/policies | Centralized `data.py`; no external policy |
| Correct next action | Structured action objects + simulated action record |
| Angry/confused customer | Brief acknowledgement then resolution |
| Escalate missing authority | Legal/formal complaint and >₹1,500 waiver paths |
| Clear conversation/action record | Timestamped Action Record tab |

## Manual acceptance tests
1. Priya: `I'm furious. I want a full cash refund plus a free business-class upgrade on my return.`
2. Arvind: `I'm frustrated about missing my meeting. Give me a hotel.`
3. Meher: `I want a full-night hotel and a different higher-fare flight. The fare difference is ₹2,000.`
4. Legal: `I am going to take legal action and file a formal complaint.`
5. Refund destination: `Refund me to a different card.`
6. Missing amount: `Move me to a different higher-fare flight.`

## Limitations
- No real booking, CRM, payment, voucher, lounge, hotel, or inventory API was supplied, so actions are simulated records.
- Intent recognition is intentionally small and deterministic; it is designed for this exercise, not arbitrary airline support.
- Exact 3-hour and 5-hour boundaries are not explicitly defined by the supplied wording; the engine escalates such a boundary instead of inventing a rule.
- Data/audit history is in-memory and session-scoped; production would use authenticated context and durable storage.

## Production evolution
Add authenticated customer lookup, durable audit storage, airline/CRM adapters, observability, and optionally an LLM intent layer with structured output. Keep policy/authority decisions deterministic and independently tested.

## Two-minute demo
1. Priya: show combined refund + upgrade handling.
2. Arvind: show the 4-hour hotel threshold decision.
3. Meher: show partial resolution + ₹2,000 supervisor escalation.
4. Show Action Record.
5. Explain that external actions are deliberately simulated because no airline API was supplied.
