"""Supplied assignment data only. No external airline facts are added."""
EXERCISE_DATE = "Wednesday, 23 September 2026"
CUSTOMERS = {
    "Priya Nair": {"tier":"Gold","pnr":"SK4821X","contact":"priya.nair@example.com, +91-98xxxxxxx1","history":"6 flights, 1 prior complaint (delayed baggage, resolved with voucher)","flights":{
        "SK-204":{"route":"Delhi → Goa","date":"Wed 23 Sep 2026","scheduled_departure":"18:40","status":"cancelled","status_display":"Cancelled (operational reasons)","cause":"airline","delay_hours":0},
        "Return":{"route":"Goa → Delhi","date":"Fri 25 Sep 2026","scheduled_departure":"16:20","status":"unaffected","status_display":"Unaffected","cause":None,"delay_hours":0}}},
    "Arvind Kulkarni": {"tier":"Silver","pnr":"TR1190B","contact":"arvind.kulkarni@example.com, +91-98xxxxxxx2","history":"3 flights, no prior complaints","flights":{
        "SK-118":{"route":"Mumbai → Bengaluru","date":"Wed 23 Sep 2026","scheduled_departure":"07:10","status":"delayed","status_display":"Delayed 4h (new departure 11:10)","new_departure":"11:10","cause":"airline","delay_hours":4}}},
    "Meher Kaur": {"tier":"Platinum","pnr":"WL7742","contact":"meher.kaur@example.com, +91-98xxxxxxx3","history":"10 flights, 1 prior complaint (overbooking, resolved with a tier-status upgrade)","flights":{
        "SK-305":{"route":"Delhi → Hyderabad","date":"Wed 23 Sep 2026","scheduled_departure":"14:00","status":"delayed","status_display":"Delayed 6h (new departure 20:00)","new_departure":"20:00","cause":"airline","delay_hours":6}}}
}
POLICY = {
 "cancellation":"Airline-caused cancellation: free rebooking on the next available flight within 24 hours OR a full refund, customer's choice.",
 "delay_under_3":"Delay under 3 hours: ₹500 meal voucher.",
 "delay_over_3":"Delay more than 3 hours: meal voucher + lounge access.",
 "delay_over_5":"Delay more than 5 hours: meal voucher + hotel accommodation covering only delayed hours, not a full night's stay.",
 "refund":"Refunds for airline-caused cancellations are processed in full within 7 business days to the original payment method only.",
 "fare_difference":"Voluntary higher-fare rebooking requires the fare difference. Agents cannot waive fare differences above ₹1,500 without supervisor approval.",
 "loyalty":"Gold and Platinum customers receive priority rebooking, but no additional compensation beyond standard policy."
}
