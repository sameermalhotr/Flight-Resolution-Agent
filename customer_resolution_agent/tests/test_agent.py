import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent import resolve
def a(r,t): return [x for x in r.actions if x.action_type==t]
def test_priya_combined():
    r=resolve("Priya Nair","I'm furious. I want a full cash refund plus a free business class upgrade.")
    assert a(r,"refund")[0].status=="initiated" and a(r,"extra_compensation")[0].status=="not_authorized"
def test_alt_refund_method():
    assert a(resolve("Priya Nair","Refund me to a different card."),"refund")[0].status=="blocked"
def test_mutually_exclusive_cancel_options():
    r=resolve("Priya Nair","I want a refund and rebook me.")
    assert a(r,"choice_required")[0].status=="pending" and a(r,"refund")[0].status=="pending_choice"
def test_arvind_hotel():
    r=resolve("Arvind Kulkarni","I want a hotel.")
    assert a(r,"hotel")[0].status=="not_eligible" and a(r,"lounge_access")[0].status=="eligible"
def test_meher_full_night():
    r=resolve("Meher Kaur","I want a full night hotel.")
    assert a(r,"full_night_hotel")[0].status=="not_authorized" and a(r,"hotel")[-1].status=="arranged"
def test_meher_2000():
    r=resolve("Meher Kaur","Move me to a different flight. The fare difference is ₹2,000.")
    assert r.escalation=="supervisor" and a(r,"fare_waiver")[0].status=="escalated"
def test_missing_amount():
    r=resolve("Meher Kaur","Move me to a different higher fare flight.")
    assert a(r,"fare_difference")[0].status=="information_required"
def test_legal():
    assert resolve("Arvind Kulkarni","I will take legal action.").escalation=="specialist_support"
def test_empty():
    assert a(resolve("Priya Nair","   "),"validation")[0].status=="blocked"
def test_unknown():
    assert a(resolve("Unknown","refund"),"validation")[0].status=="blocked"


def test_unrelated_or_unclear_message_does_not_default_to_cancellation_resolution():
    r=resolve("Priya Nair","hgh gh")
    assert r.intents == []
    assert a(r,"clarification")[0].status == "required"
    assert "What would you like help with" in r.message
