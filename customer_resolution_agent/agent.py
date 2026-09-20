"""Deterministic, auditable resolution engine for the supplied interview exercise."""
from dataclasses import dataclass, field
import re
from typing import List, Dict, Optional
from data import CUSTOMERS

LEGAL_TERMS=("legal action","formal complaint","lawyer","solicitor","sue","court")
ANGER_TERMS=("furious","angry","unacceptable","ridiculous","frustrated","upset","terrible")
REFUND_TERMS=("refund","money back","cash back")
REBOOK_TERMS=("rebook","another flight","different flight","move me","next flight")
UPGRADE_TERMS=("upgrade","business class","first class")
HOTEL_TERMS=("hotel","accommodation","full night","night's stay","night stay")
ALT_PAYMENT_TERMS=("different card","another card","different account","bank transfer")

@dataclass
class Action:
    action_type: str
    status: str
    detail: str

@dataclass
class Resolution:
    message: str
    actions: List[Action]=field(default_factory=list)
    escalation: Optional[str]=None
    intents: List[str]=field(default_factory=list)

def _contains(text, terms): return any(term in text for term in terms)

def _money_amount(text):
    for p in [r"₹\s*([\d,]+)",r"\brs\.?\s*([\d,]+)",r"\binr\s*([\d,]+)",r"\bfare difference(?:\s+is|\s+of|:)?\s*([\d,]+)",r"\bdifference(?:\s+is|\s+of|:)?\s*([\d,]+)"]:
        m=re.search(p,text,re.I)
        if m: return int(m.group(1).replace(",",""))
    return None

def _main_flight(customer):
    for no,f in customer["flights"].items():
        if f["status"] in ("cancelled","delayed"): return no,f
    return next(iter(customer["flights"].items()))

def resolve(customer_name, raw_message):
    if customer_name not in CUSTOMERS:
        return Resolution("I can't find that customer in the supplied exercise data.",[Action("validation","blocked","Unknown customer")])
    message=(raw_message or "").strip()
    if not message:
        return Resolution("Please enter a message so I can understand what help is needed.",[Action("validation","blocked","Empty customer message")])

    text=message.lower(); c=CUSTOMERS[customer_name]; flight_no,flight=_main_flight(c)
    prefix="I understand this is frustrating. " if _contains(text,ANGER_TERMS) else ""

    if _contains(text,LEGAL_TERMS):
        return Resolution(prefix+"Because you've mentioned legal action or a formal complaint, this must be escalated immediately to specialist support. I've recorded the escalation.",
            [Action("escalation","created","Legal action/formal complaint requires immediate human escalation")],"specialist_support",["legal_or_formal_complaint"])

    refund=_contains(text,REFUND_TERMS); rebook=_contains(text,REBOOK_TERMS); upgrade=_contains(text,UPGRADE_TERMS)
    hotel=_contains(text,HOTEL_TERMS); alt_payment=_contains(text,ALT_PAYMENT_TERMS); amount=_money_amount(text)
    intents=[name for name,flag in [("refund",refund),("rebook",rebook),("upgrade",upgrade),("hotel",hotel),("alternate_refund_method",alt_payment)] if flag]

    # Do not assume the customer is asking about the disruption merely because their
    # booking is disrupted. Unrelated/unclear text must trigger clarification.
    if not intents:
        status_summary = (
            f"Your {flight_no} flight is cancelled." if flight["status"] == "cancelled"
            else f"Your {flight_no} flight is delayed {flight['delay_hours']} hours."
        )
        return Resolution(
            f"I can help with your booking. {status_summary} "
            "What would you like help with — refund, rebooking, compensation, or another issue?",
            [Action("clarification", "required", "Customer intent not identified from message")],
            intents=[]
        )

    if flight["status"]=="cancelled":
        actions=[]; parts=[prefix+f"I can see {flight_no} ({flight['route']}) was cancelled for operational reasons."]
        if alt_payment and refund:
            actions.append(Action("refund","blocked","Refund cannot be sent to a different payment method"))
            parts.append("A full refund is available, but policy requires it to go to the original payment method; I cannot process it to a different method.")
        elif refund:
            actions.append(Action("refund","initiated",f"Full refund for {flight_no}; original payment method; within 7 business days"))
            parts.append("I've initiated the full refund request. It will be processed within 7 business days to the original payment method.")
        if rebook:
            priority=c["tier"] in ("Gold","Platinum")
            actions.append(Action("rebooking","requested",f"Free next-available rebooking within 24 hours for {flight_no}"+("; priority rebooking applies" if priority else "")))
            parts.append("Free rebooking on the next available flight within 24 hours is available"+(" with priority access because of your loyalty tier." if priority else "."))
        if upgrade:
            actions.append(Action("extra_compensation","not_authorized","Free business-class upgrade is not provided by supplied policy"))
            parts.append("The supplied policy does not authorize a free business-class upgrade as additional compensation.")
        if refund and rebook:
            actions.append(Action("choice_required","pending","Cancellation policy offers refund OR free rebooking"))
            for a in actions:
                if a.action_type in ("refund","rebooking"): a.status="pending_choice"
            parts.append("Because cancellation policy offers a refund OR rebooking, please choose which one you want me to proceed with.")
        elif not refund and not rebook:
            parts.append("You can choose either free rebooking on the next available flight within 24 hours or a full refund. Which would you prefer?")
        return Resolution(" ".join(parts),actions,intents=intents)

    delay=flight["delay_hours"]; actions=[]; parts=[prefix+f"I can see {flight_no} ({flight['route']}) is delayed {delay} hours."]
    if delay < 3:
        actions.append(Action("meal_voucher","eligible","₹500 meal voucher")); parts.append("This qualifies for a ₹500 meal voucher.")
    elif delay > 5:
        actions += [Action("meal_voucher","eligible","Meal voucher"),Action("lounge_access","eligible","Lounge access"),Action("hotel","eligible",f"Accommodation covering only the {delay} delayed hours")]
        parts.append("This qualifies for a meal voucher, lounge access, and hotel accommodation covering only the delayed hours.")
    elif delay > 3:
        actions += [Action("meal_voucher","eligible","Meal voucher"),Action("lounge_access","eligible","Lounge access")]
        parts.append("This qualifies for a meal voucher and lounge access.")
    else:
        actions.append(Action("policy_gap","escalated",f"Exact {delay}-hour boundary is not explicitly defined"))
        return Resolution(" ".join(parts)+f" The supplied policy does not explicitly define the exact {delay}-hour boundary, so I won't invent a rule. I'm escalating this boundary case for human review.",actions,"policy_review",intents)

    if hotel and delay <= 5:
        actions.append(Action("hotel","not_eligible","Hotel requires a delay of more than 5 hours"))
        parts.append("Hotel accommodation is not available under the supplied policy because the delay is not more than 5 hours.")
    elif hotel and delay > 5:
        if any(x in text for x in ("full night","night's stay","night stay")):
            actions.append(Action("full_night_hotel","not_authorized","Policy covers delayed hours only"))
            parts.append("A full night's stay is not covered; the hotel benefit is limited to the delayed-hours portion.")
        actions.append(Action("hotel","arranged",f"Policy-covered accommodation for {delay} delayed hours"))
        parts.append("I've recorded the policy-covered hotel arrangement.")

    if rebook:
        if amount is None:
            actions.append(Action("fare_difference","information_required","Fare difference amount not supplied"))
            parts.append("For a voluntary higher-fare flight, the fare difference applies. I need the fare-difference amount to determine whether a waiver request is within agent authority.")
        elif amount > 1500:
            actions.append(Action("fare_waiver","escalated",f"₹{amount:,} exceeds ₹1,500 agent waiver authority"))
            parts.append(f"The ₹{amount:,} fare-difference waiver exceeds the agent's ₹1,500 authority, so I've escalated that waiver request to a supervisor.")
            return Resolution(" ".join(parts),actions,"supervisor",intents)
        else:
            actions.append(Action("fare_difference","payable",f"Voluntary rebooking fare difference: ₹{amount:,}"))
            parts.append(f"The supplied rule says the ₹{amount:,} fare difference is payable for a voluntary higher-fare rebooking. No waiver is assumed.")
    return Resolution(" ".join(parts),actions,intents=intents)
