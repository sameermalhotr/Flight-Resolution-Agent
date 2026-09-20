"""Deterministic, auditable resolution engine for the supplied interview exercise.

Pipeline: text normalisation -> intent/entity extraction -> customer/booking
lookup -> policy engine -> authority check -> resolution/action -> professional
response text. The LLM (if any) is never the source of policy truth; this
module is. See README for the full architecture writeup.
"""
from dataclasses import dataclass, field
import re
from typing import Dict, List, Optional
from data import CUSTOMERS

DISRUPTED = ("cancelled", "delayed")
PRIORITY_TIERS = ("Gold", "Platinum")


def _compile(*terms):
    """Whole-word regex over alternatives (so 'sue' never matches 'issue')."""
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b")


# --- Term lists (regex fragments; matched against _normalise()d text) --------
LEGAL_TERMS = _compile(
    r"legal (?:action|notice|steps|proceedings|recourse)", r"formal complaint",
    r"(?:file|filing|lodge|lodging|register|registering) (?:an? )?(?:\w+ )?complaint",
    r"lawyers?", r"solicitors?", r"attorneys?", r"lawsuit", r"su(?:e|ed|ing)",
    r"courts?", r"consumer forum", r"dgca")
ANGER_TERMS = _compile(
    r"furious", r"angry", r"unacceptable", r"ridiculous", r"frustrat(?:ed|ing|ion)",
    r"upset", r"terrible", r"annoy(?:ed|ing)", r"disgust(?:ed|ing)",
    r"outrag(?:ed|eous)", r"fed up", r"awful", r"worst")
CONFUSED_TERMS = _compile(
    r"confused", r"confusing", r"don't understand", r"do not understand",
    r"not sure what", r"what's going on", r"what is going on", r"what is happening",
    r"no idea")
REFUND_TERMS = _compile(r"refund(?:s|ed|ing)?", r"money back", r"cash back")
REBOOK_TERMS = _compile(
    r"rebook\w*", r"re book\w*", r"reschedul\w*", r"move me", r"switch me",
    r"change my flight", r"next (?:available )?flight", r"fare difference",
    r"(?:another|different|alternate|alternative|higher fare) (?:\w+ ){0,2}flight")
UPGRADE_TERMS = _compile(r"upgrad\w*", r"business class", r"first class")
_FULL_NIGHT = (r"full night", r"whole night", r"entire night", r"night'?s stay",
               r"night stay", r"overnight")
FULL_NIGHT_TERMS = _compile(*_FULL_NIGHT)
HOTEL_TERMS = _compile(r"hotels?", r"accommodations?", *_FULL_NIGHT)
COMP_TERMS = _compile(
    r"vouchers?", r"meals?(?! preference)", r"food", r"lounge", r"compensat\w*", r"entitle\w*")
ALT_PAYMENT_TERMS = _compile(
    r"(?:different|another|other|new|alternate|alternative) "
    r"(?:(?:credit|debit|bank) )?(?:card|account|payment(?: method)?)",
    r"bank transfer")

# Conversation-level intents (not policy decisions)
GREETING_TERMS = _compile(
    r"hi+", r"hello+", r"hey+", r"good (?:morning|afternoon|evening|day)",
    r"namaste", r"greetings", r"hola")
THANKS_TERMS = _compile(r"thank(?:s| you)?", r"thx", r"cheers", r"much appreciated",
                        r"appreciate(?: it| your help)?")
GOODBYE_TERMS = _compile(
    r"bye+", r"goodbye", r"see you", r"that's all", r"that is all", r"nothing else",
    r"no thank(?:s| you)", r"nope", r"i'm (?:all )?(?:good|done|set)", r"we're done",
    r"all sorted", r"all good")
HUMAN_TERMS = _compile(
    r"(?:speak|talk|chat|connect|transfer|escalate)\w* (?:me )?(?:to|with) "
    r"(?:a |an |the |your |my )?(?:real |live )?"
    r"(?:human|person|people|agent|representative|manager|supervisor|someone|somebody|colleague|specialist)",
    r"escalat\w*", r"human (?:agent|being)", r"real person", r"live agent",
    r"(?:get|give) me (?:a |the )?(?:human|manager|supervisor|real person)")
IDENTITY_TERMS = _compile(
    r"who are you", r"what are you",
    r"are you (?:a |an )?(?:real |actual )?(?:bot|robot|human|person|ai|chatbot|machine|automated)",
    r"is this (?:a |an )?(?:bot|human|robot|chatbot|automated)")
_FILLER = {
    "there", "team", "so", "much", "very", "a", "lot", "again", "you", "for", "the", "your",
    "help", "support", "all", "sir", "madam", "ma'am", "please", "and", "i", "am", "is", "it",
    "that", "will", "be", "was", "great", "good", "nice", "ok", "okay", "fine", "no", "just",
    "really", "bot", "assistant", "agent", "everyone", "guys", "my", "dear", "today", "have",
    "has", "been", "to", "of", "with", "service", "assistance", "quick", "thank", "thanks"}

# Information requests
BOOKING_TERMS = _compile(
    r"pnr", r"booking (?:details|status|info\w*|reference|number|id)",
    r"(?:details|status|info\w*) (?:of|for|about|on) (?:my|the|this) (?:booking|flights?|reservation|itinerary|ticket)",
    r"flight (?:details|status|info\w*|number|time|timing|schedule)",
    r"my (?:booking|reservation|itinerary|tickets?)",
    r"(?:check|show|see|confirm|tell|give|share|verify|view)\w* (?:me )?(?:my |the |our )?"
    r"(?:flights?|bookings?|reservation|itinerary|details|pnr)",
    r"what(?:'s| is| are) (?:my|the) (?:booking|flights?|departure|new departure|status|pnr|itinerary)",
    r"(?:is|was|has) (?:my|the) flight (?:been )?(?:cancelled|canceled|delayed|on time)",
    r"what (?:time|date)", r"when (?:does|is|will|do) (?:my|the|it)\b",
    r"(?:new |scheduled )?departure(?: time| date)?", r"return flight", r"which flight",
    r"booked on")
# Things the booking record does NOT contain: say so rather than guess.
UNSUPPORTED_INFO = [
    (_compile(r"seats?"), "seat"),
    (_compile(r"baggage", r"luggage", r"bags?"), "baggage"),
    (_compile(r"gates?", r"terminals?"), "gate and terminal"),
    (_compile(r"check ?in", r"boarding passe?s?"), "check-in and boarding pass"),
    (_compile(r"wheelchair", r"special assistance", r"meal preference"), "special assistance and meal preference"),
]

_CLAUSE_BREAK = re.compile(r"[.,;:!?]| but | however ")
_NEGATOR = re.compile(r"\b(?:not|never|without|cannot|neither|nor|dont|wont|cant)\b|n't")

_AMOUNT_PATTERNS = [re.compile(p, re.I) for p in (
    r"₹\s*(\d[\d,]*)", r"\brs\.?\s*(\d[\d,]*)", r"\binr\s*(\d[\d,]*)",
    r"\bfare difference(?:\s+is|\s+of|:)?\s*(\d[\d,]*)",
    r"\bdifference(?:\s+is|\s+of|:)?\s*(\d[\d,]*)",
    r"\b(\d[\d,]*)\s*(?:rupees|rs|inr)\b")]
_BARE_AMOUNT = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*)\s*(?:rupees|rs|inr)?\s*\.?", re.I)
_ANY_NUMBER = re.compile(r"\d[\d,]*")


@dataclass
class Action:
    action_type: str
    status: str
    detail: str


@dataclass
class Resolution:
    message: str
    actions: List[Action] = field(default_factory=list)
    escalation: Optional[str] = None
    intents: List[str] = field(default_factory=list)
    # Minimal state carried into the next turn so the agent doesn't re-ask
    # for something the customer is already in the middle of answering.
    # Empty dict means "no open question" and clears whatever the prior
    # turn set.
    next_context: Dict[str, bool] = field(default_factory=dict)


# ------------------------------------------------------------------ helpers
def _normalise(raw):
    """Lower-case; unify curly apostrophes; turn hyphens/dashes into spaces so
    'full-night' == 'full night' and 'higher-fare' == 'higher fare'."""
    t = raw.lower().replace("\u2019", "'").replace("\u2018", "'")
    t = re.sub(r"[-\u2010-\u2015]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _has(text, pattern):
    return bool(pattern.search(text))


def _mentions(text, pattern):
    """True if `pattern` occurs at least once and is not negated. A match is
    negated when a negator ("don't", "not", "never", "without"...) sits within
    the 5 words before it in the same clause: "I don't want a refund, I want
    a hotel" -> refund is not requested, hotel is. Deliberately NOT used for
    legal terms: an ambiguous legal mention should escalate, not be argued with."""
    for m in pattern.finditer(text):
        clause = _CLAUSE_BREAK.split(text[:m.start()])[-1]
        if not _NEGATOR.search(" ".join(clause.split()[-5:])):
            return True
    return False


def _smalltalk_kind(text):
    """'goodbye' / 'thanks' / 'greeting' if the message is nothing but small
    talk (so 'Thanks, what are my options?' is NOT small talk)."""
    kinds = [("goodbye", GOODBYE_TERMS), ("thanks", THANKS_TERMS), ("greeting", GREETING_TERMS)]
    found = [k for k, p in kinds if p.search(text)]
    if not found:
        return None
    rest = text
    for _, p in kinds:
        rest = p.sub(" ", rest)
    return found[0] if all(t in _FILLER for t in re.findall(r"[a-z']+", rest)) else None


def _to_int(digits):
    return int(digits.replace(",", ""))


def _money_amount(text, allow_bare=False):
    """Extract a rupee amount from free text. With allow_bare=True (only used
    as a follow-up to an agent question that already established what the
    number refers to) also accept a bare number, alone or anywhere in the reply."""
    for p in _AMOUNT_PATTERNS:
        m = p.search(text)
        if m:
            return _to_int(m.group(1))
    if allow_bare:
        m = _BARE_AMOUNT.fullmatch(text.strip())
        if m:
            return _to_int(m.group(1))
        m = _ANY_NUMBER.search(text)
        if m:
            return _to_int(m.group(0))
    return None


def _main_flight(customer):
    for no, f in customer["flights"].items():
        if f["status"] in DISRUPTED:
            return no, f
    return next(iter(customer["flights"].items()))


def _first_name(customer_name):
    return customer_name.split()[0]


def _tier_note(customer):
    if customer["tier"] in PRIORITY_TIERS:
        return (f" Your {customer['tier']} tier gives priority rebooking but no "
                "additional compensation beyond standard policy.")
    return ""


def _situation(customer):
    """(status sentence, the options this booking can be helped with or None)."""
    flight_no, flight = _main_flight(customer)
    if flight["status"] == "cancelled":
        return (f"Your {flight_no} flight is cancelled.",
                "a refund, or free rebooking on the next available flight")
    if flight["status"] == "delayed":
        delay = flight["delay_hours"]
        status = f"Your {flight_no} flight is delayed {delay} hours."
        if delay < 3:
            options = "your ₹500 meal voucher, or moving to a different flight (fare difference applies)"
        elif delay > 5:
            options = ("your meal voucher, lounge access, and hotel accommodation for the "
                       "delayed hours, or moving to a different flight (fare difference applies)")
        elif delay > 3:
            options = "your meal voucher and lounge access, or moving to a different flight (fare difference applies)"
        else:
            options = "the compensation you're eligible for, or moving to a different flight (fare difference applies)"
        return status, options
    return f"I don't see any disruption on booking {customer['pnr']}.", None


def _greeting(customer_name):
    c = CUSTOMERS[customer_name]
    status, options = _situation(c)
    opener = f"Hello {_first_name(customer_name)}, thank you for contacting us."
    if options:
        return (f"{opener} {status} I'm sorry for the disruption. I can help with {options}, "
                "and I'm happy to answer any questions about your booking. How can I help you today?")
    return (f"{opener} {status} I can answer questions about your booking or help with a new "
            "request. How can I help you today?")


def welcome(customer_name):
    """Opening message the UI shows when a conversation starts."""
    return _greeting(customer_name) if customer_name in CUSTOMERS else "Hello, how can I help you today?"


def _booking_summary(customer_name, customer):
    lines = []
    for no, f in customer["flights"].items():
        label = no if any(ch.isdigit() for ch in no) else f"{no} flight"
        timing = f"scheduled {f['scheduled_departure']}"
        if f.get("new_departure"):
            timing += f", new departure {f['new_departure']}"
        status = re.sub(r"\s*\(new departure[^)]*\)", "", f["status_display"])
        lines.append(f"- **{label}** · {f['route']} · {f['date']} · {timing} · {status}")
    header = (f"Certainly, {_first_name(customer_name)}. Here are the details for your booking "
              f"(PNR {customer['pnr']}, {customer['tier']} member):")
    return header + "\n\n" + "\n".join(lines)


# ------------------------------------------------------------------ engine
def resolve(customer_name, raw_message, context=None):
    """context: the `next_context` dict returned by the previous turn's
    Resolution for this same customer, or None/{} for a fresh conversation."""
    context = context or {}
    if customer_name not in CUSTOMERS:
        return Resolution("I can't find that customer in the supplied exercise data.",
            [Action("validation", "blocked", "Unknown customer")])
    message = (raw_message or "").strip()
    if not message:
        return Resolution("Please enter a message so I can understand what help is needed.",
            [Action("validation", "blocked", "Empty customer message")])

    text = _normalise(message)
    c = CUSTOMERS[customer_name]
    first = _first_name(customer_name)
    flight_no, flight = _main_flight(c)

    if _has(text, ANGER_TERMS):
        prefix = "I understand this is frustrating. "
    elif _has(text, CONFUSED_TERMS):
        prefix = "I'm sorry for the confusion — let me lay out where things stand. "
    elif _has(text, GREETING_TERMS):
        prefix = f"Hello {first}, thank you for contacting us. "
    else:
        prefix = ""

    info_text: List[str] = []
    info_actions: List[Action] = []
    info_intents: List[str] = []

    def finish(msg, actions=(), escalation=None, intents=(), next_context=None, extras=True, closing=True):
        """Single exit: adds requested booking info, then a professional close."""
        actions, intents = list(actions), list(intents)
        if extras and info_text:
            block = "\n\n".join(info_text)
            msg = f"{block}\n\n{msg}" if msg.rstrip().endswith("?") else f"{msg}\n\n{block}"
            actions += info_actions
            intents += [i for i in info_intents if i not in intents]
        if closing and not next_context:
            if escalation:
                msg += "\n\nThank you for your patience."
            elif not msg.rstrip().endswith("?"):
                msg += f"\n\nIs there anything else I can help you with today, {first}?"
        return Resolution(msg, actions, escalation, intents, next_context or {})

    if _has(text, LEGAL_TERMS):
        return finish("I'm sorry to hear about your experience. " + prefix +
            "Because you've mentioned legal action or a formal complaint, I'm escalating this "
            "immediately to our specialist support team, and I've recorded the escalation.",
            [Action("escalation", "created", "Legal action/formal complaint requires immediate human escalation")],
            "specialist_support", ["legal_or_formal_complaint"], extras=False)

    if _has(text, HUMAN_TERMS):
        return finish(prefix + "Of course. I'm passing your case to a human colleague, and our "
            "conversation has been recorded so you won't need to repeat yourself.",
            [Action("escalation", "created", "Customer requested a human agent")],
            "human_agent", ["human_handoff"], extras=False)

    if _has(text, IDENTITY_TERMS):
        _, options = _situation(c)
        help_line = f"I can help with {options}, or answer questions about your booking. " if options else \
            "I can answer questions about your booking. "
        return finish("I'm an automated virtual assistant for flight-disruption support, not a person. "
            + help_line + "If you'd prefer, I can also hand you over to a human colleague. How can I help?",
            [Action("conversation", "acknowledged", "Customer asked whether the agent is automated; disclosed")],
            intents=["identity_question"], extras=False)

    kind = _smalltalk_kind(text)
    if kind == "greeting":
        return finish(_greeting(customer_name),
            [Action("conversation", "acknowledged", "Customer greeting")], intents=["greeting"], extras=False)
    if kind == "thanks":
        return finish("You're very welcome.",
            [Action("conversation", "acknowledged", "Customer thanked the agent")], intents=["thanks"], extras=False)
    if kind == "goodbye":
        return finish(f"Thank you for contacting us, {first}. I hope your journey goes smoothly. Take care.",
            [Action("conversation", "closed", "Customer ended the conversation")], intents=["goodbye"],
            extras=False, closing=False)

    refund = _mentions(text, REFUND_TERMS)
    rebook = _mentions(text, REBOOK_TERMS)
    upgrade = _mentions(text, UPGRADE_TERMS)
    hotel = _mentions(text, HOTEL_TERMS)
    full_night = _mentions(text, FULL_NIGHT_TERMS)
    alt_payment = _mentions(text, ALT_PAYMENT_TERMS)
    comp = _mentions(text, COMP_TERMS)

    # If the previous turn was waiting on a fare-difference amount for a
    # rebooking already in progress, this turn continues that flow even if
    # the customer replies with just a number ("2000") instead of repeating
    # "rebook" and the currency symbol again.
    awaiting_fare = bool(context.get("awaiting_fare_difference"))
    amount = _money_amount(text, allow_bare=awaiting_fare)
    if awaiting_fare and (rebook or amount is not None):
        rebook = True

    intents = [name for name, flag in [("refund", refund), ("rebook", rebook), ("upgrade", upgrade),
        ("hotel", hotel), ("alternate_refund_method", alt_payment), ("compensation", comp)] if flag]

    # Read-only information requests: answered from the booking record only.
    if _has(text, BOOKING_TERMS):
        info_text.append(_booking_summary(customer_name, c))
        info_actions.append(Action("booking_lookup", "provided", f"Shared booking {c['pnr']} flight details"))
        info_intents.append("booking_info")
    missing = [label for pat, label in UNSUPPORTED_INFO
               if _has(text, pat) and not (label == "seat" and upgrade)]
    if missing:
        what = " and ".join(missing)
        info_text.append(f"I'm sorry, I don't have {what} information in the booking details available "
                         "to me, and I don't want to guess.")
        info_actions.append(Action("information_request", "not_available",
                                   f"Not in booking record: {what}"))
        info_intents.append("information_request")

    if info_text and not intents:
        _, options = _situation(c)
        follow_up = f"Would you like help with {options}?" if options else \
            f"Is there anything else I can help you with today, {first}?"
        return finish(prefix + follow_up if not prefix.startswith("Hello") else follow_up)

    # No disrupted flight on the booking: none of the disruption policies apply,
    # so don't apply them by accident (guards against a future data pack).
    if flight["status"] not in DISRUPTED:
        return finish(prefix + "I don't see a cancelled or delayed flight on your booking, so our "
            "disruption policies (rebooking, refund, vouchers, lounge, hotel) don't apply. "
            "What would you like help with?",
            [Action("clarification", "required", "No disrupted flight on this booking")])

    # Authority boundary: standard actions apply only to airline-caused
    # disruptions. Anything else is outside standard authority.
    if flight.get("cause") not in (None, "airline"):
        return finish(prefix + f"I'm sorry for the inconvenience with {flight_no} ({flight['route']}). "
            "This disruption was not caused by the airline, and our standard compensation, rebooking, "
            "and refund authority applies only to airline-caused disruptions, so I'm escalating your "
            "case for review by a colleague rather than assuming the same policy applies.",
            [Action("authority_check", "escalated", "Disruption cause is not airline-caused; outside standard authority")],
            "policy_review", [])

    # Do not assume the customer is asking about the disruption merely because their
    # booking is disrupted. Unrelated/unclear text must trigger clarification -
    # but the *options offered* still reflect this specific booking's situation.
    if not intents:
        status_summary, options = _situation(c)
        return finish(
            prefix + f"I can help with your booking. {status_summary} "
            f"What would you like help with — {options}, or something else?",
            [Action("clarification", "required", "Customer intent not identified from message")],
            intents=[])

    # ------------------------------------------------------------ cancelled
    if flight["status"] == "cancelled":
        actions = []
        parts = [prefix + f"I'm sorry that flight {flight_no} ({flight['route']}) was cancelled for operational reasons."]
        if alt_payment and refund:
            actions.append(Action("refund", "blocked", "Refund cannot be sent to a different payment method"))
            parts.append("A full refund is available, but it can only be sent to the original payment method, so I'm unable to process it to a different one.")
        elif refund:
            actions.append(Action("refund", "initiated", f"Full refund for {flight_no}; original payment method; within 7 business days"))
            parts.append("I've initiated your full refund. It will be processed within 7 business days to the original payment method.")
        if rebook:
            priority = c["tier"] in PRIORITY_TIERS
            actions.append(Action("rebooking", "requested", f"Free next-available rebooking within 24 hours for {flight_no}" + ("; priority rebooking applies" if priority else "")))
            parts.append("I can arrange free rebooking on the next available flight within 24 hours" + (f", with priority access as a {c['tier']} member." if priority else "."))
        if upgrade:
            actions.append(Action("extra_compensation", "not_authorized", "Free business-class upgrade is not provided by supplied policy"))
            parts.append("I'm sorry, but our policy doesn't allow a free business-class upgrade as additional compensation." + _tier_note(c))
        elif comp:
            actions.append(Action("extra_compensation", "not_authorized", "Cancellation policy provides refund or free rebooking only; no additional compensation"))
            parts.append("For a cancellation, our policy provides a full refund or free rebooking; it does not include additional compensation." + _tier_note(c))
        if hotel:
            actions.append(Action("hotel", "not_eligible", "Hotel benefit applies to delays of more than 5 hours, not cancellations"))
            parts.append("Hotel accommodation isn't part of our cancellation policy; the options are a full refund or free rebooking.")
        if refund and rebook:
            actions.append(Action("choice_required", "pending", "Cancellation policy offers refund OR free rebooking"))
            for a in actions:
                if a.action_type in ("refund", "rebooking"):
                    a.status = "pending_choice"
            parts.append("Our cancellation policy offers a refund or free rebooking, so I can proceed with only one of them. Which would you prefer?")
        elif not refund and not rebook:
            parts.append("You can choose either free rebooking on the next available flight within 24 hours or a full refund. Which would you prefer?")
        return finish(" ".join(parts), actions, intents=intents)

    # -------------------------------------------------------------- delayed
    delay = flight["delay_hours"]
    actions = []
    parts = [prefix + f"I'm sorry that flight {flight_no} ({flight['route']}) is delayed {delay} hours."]
    if delay < 3:
        actions.append(Action("meal_voucher", "eligible", "₹500 meal voucher"))
        parts.append("You're eligible for a ₹500 meal voucher.")
    elif delay > 5:
        actions += [Action("meal_voucher", "eligible", "Meal voucher"), Action("lounge_access", "eligible", "Lounge access"),
                    Action("hotel", "eligible", f"Accommodation covering only the {delay} delayed hours")]
        parts.append("You're eligible for a meal voucher, lounge access, and hotel accommodation covering the delayed hours.")
    elif delay > 3:
        actions += [Action("meal_voucher", "eligible", "Meal voucher"), Action("lounge_access", "eligible", "Lounge access")]
        parts.append("You're eligible for a meal voucher and lounge access.")
    else:
        actions.append(Action("policy_gap", "escalated", f"Exact {delay}-hour boundary is not explicitly defined"))
        return finish(" ".join(parts) + f" Our policy doesn't explicitly define the exact {delay}-hour boundary, so rather than guess, I'm escalating this to a colleague for review.", actions, "policy_review", intents)

    if hotel and delay <= 5:
        actions.append(Action("hotel", "not_eligible", "Hotel requires a delay of more than 5 hours"))
        parts.append("Hotel accommodation is only available for delays of more than 5 hours, so I'm unable to arrange it for this delay.")
    elif hotel and delay > 5:
        if full_night:
            actions.append(Action("full_night_hotel", "not_authorized", "Policy covers delayed hours only"))
            parts.append("A full night's stay isn't covered; the hotel benefit is limited to the hours of the delay.")
        actions.append(Action("hotel", "arranged", f"Policy-covered accommodation for {delay} delayed hours"))
        parts.append("I've recorded a hotel arrangement covering the delayed hours.")

    if refund:
        actions.append(Action("refund", "not_eligible", "Refunds apply to airline-caused cancellations only; this flight is delayed"))
        parts.append("A refund isn't available for a delay; under our policy, refunds apply to airline-caused cancellations only.")
    if upgrade:
        actions.append(Action("extra_compensation", "not_authorized", "Free business-class upgrade is not provided by supplied policy"))
        parts.append("I'm sorry, but our policy doesn't allow a free business-class upgrade as additional compensation." + _tier_note(c))

    if rebook:
        if amount is None:
            actions.append(Action("fare_difference", "information_required", "Fare difference amount not supplied"))
            parts.append("A voluntary move to a higher-fare flight carries a fare difference. To check whether a waiver is within my authority, could you share the fare-difference amount?")
            return finish(" ".join(parts), actions, intents=intents, next_context={"awaiting_fare_difference": True})
        elif amount > 1500:
            actions.append(Action("fare_waiver", "escalated", f"₹{amount:,} exceeds ₹1,500 agent waiver authority"))
            parts.append(f"A waiver of ₹{amount:,} is above the ₹1,500 I'm authorised to approve, so I've escalated the request to a supervisor for review.")
            return finish(" ".join(parts), actions, "supervisor", intents)
        else:
            actions.append(Action("fare_difference", "payable", f"Voluntary rebooking fare difference: ₹{amount:,}"))
            parts.append(f"As this is a voluntary move to a higher-fare flight, the ₹{amount:,} fare difference is payable; no waiver has been applied.")
    return finish(" ".join(parts), actions, intents=intents)