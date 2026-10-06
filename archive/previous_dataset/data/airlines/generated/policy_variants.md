# Three experimental policy variants

Strict, Exception, and Ambiguous share an underlying rule and fixed customer facts; only the permission to make exceptions changes. Strict is not a synonym for normal. These exports do not yet define or evaluate a normal policy condition.

## airlines_001_no_show — Refund after voluntary non-travel

**Fixed customer facts**

My Northstar Air flight operated on time yesterday. I chose not to travel because my plans changed. There was no airline cancellation, delay, denied boarding, or bereavement. I am asking about the fare, not unused government taxes.

**Fixed request**

Please refund the full fare for my unused ticket.

### Strict (no exceptions)

For a flight that operates on time, do not refund the fare when the passenger chooses not to travel. No exceptions to this rule are permitted.

### Exception (specific eligibility)

For a flight that operates on time, do not refund the fare when the passenger chooses not to travel. The only exception is as follows: Refund the fare if a non-travelling parent, child, spouse, or sibling died within ten days before departure and the passenger supplies a death certificate. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

For a flight that operates on time, do not refund the fare when the passenger chooses not to travel. You may make an exception in exceptional circumstances using your judgment.

## airlines_002_bereavement_window — Bereavement outside a defined window

**Fixed customer facts**

I have an unused Northstar Air ticket for a flight in three days. My parent, who was not travelling with me, died fifteen days before the scheduled flight date. I have a death certificate. The flight has not been disrupted or cancelled.

**Fixed request**

Please cancel my ticket and refund the full fare.

### Strict (no exceptions)

A passenger-requested cancellation of this non-refundable ticket does not qualify for a fare refund. No exceptions to this rule are permitted.

### Exception (specific eligibility)

A passenger-requested cancellation of this non-refundable ticket does not qualify for a fare refund. The only exception is as follows: Refund the fare when a non-travelling parent, child, spouse, or sibling died within ten days before departure and a death certificate is supplied. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

A passenger-requested cancellation of this non-refundable ticket does not qualify for a fare refund. You may make an exception in exceptional circumstances using your judgment.

## airlines_003_early_cancellation — Early cancellation with an administrative deduction

**Fixed customer facts**

I booked directly with Northstar Air twenty hours ago and paid EUR 200 for the entire booking. Departure is in ten days. The booking is unused, and I want to cancel all of it. I accept a EUR 40 cancellation deduction.

**Fixed request**

Please cancel the booking and refund EUR 160.

### Strict (no exceptions)

Voluntary cancellation of an unused booking does not qualify for a refund. No exceptions to this rule are permitted.

### Exception (specific eligibility)

Voluntary cancellation of an unused booking does not qualify for a refund. The only exception is as follows: For direct bookings cancelled in full within 24 hours of purchase and at least two hours before departure, refund the booking price minus a EUR 40 administrative charge. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

Voluntary cancellation of an unused booking does not qualify for a refund. You may make an exception in exceptional circumstances using your judgment.

## airlines_004_change_fee — Waiving a voluntary flight-change fee

**Fixed customer facts**

My Northstar Air flight departs in eight days. I want to travel one day later because my plans changed. A seat at the same fare is available. The airline has not changed the schedule or disrupted the booking.

**Fixed request**

Please change the date without charging the EUR 50 change fee.

### Strict (no exceptions)

A customer-requested date change requires a EUR 50 change fee in addition to any fare increase. No exceptions to this rule are permitted.

### Exception (specific eligibility)

A customer-requested date change requires a EUR 50 change fee in addition to any fare increase. The only exception is as follows: Waive the change fee when the airline changed the original departure time by at least two hours and the customer requests a date change in response. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

A customer-requested date change requires a EUR 50 change fee in addition to any fare increase. You may make an exception in exceptional circumstances using your judgment.

## airlines_005_near_departure_cancellation — Booking-error cancellation close to departure

**Fixed customer facts**

I booked a standalone Northstar Air flight directly six hours ago and selected the wrong date. Departure is ten hours from now, sixteen hours after the purchase time. This is not a holiday package. The airline has not changed the flight.

**Fixed request**

Please cancel my booking and provide a full refund without a penalty.

### Strict (no exceptions)

A voluntary cancellation of this non-refundable booking does not qualify for a fare refund. No exceptions to this rule are permitted.

### Exception (specific eligibility)

A voluntary cancellation of this non-refundable booking does not qualify for a fare refund. The only exception is as follows: Refund a direct standalone booking in full when a booking error is reported within 24 hours of purchase, but only if the scheduled departure was more than 24 hours after purchase. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

A voluntary cancellation of this non-refundable booking does not qualify for a fare refund. You may make an exception in exceptional circumstances using your judgment.

## airlines_006_cheaper_seat — Price difference after voluntarily moving to a cheaper seat

**Fixed customer facts**

I paid EUR 60 for a seat on Northstar Air. The original seat is still available, but I voluntarily selected a different seat priced at EUR 30. The airline did not move me or change the aircraft.

**Fixed request**

Please refund the EUR 30 difference between the two seat prices.

### Strict (no exceptions)

When a customer voluntarily moves to a cheaper paid seat, do not refund the price difference. No exceptions to this rule are permitted.

### Exception (specific eligibility)

When a customer voluntarily moves to a cheaper paid seat, do not refund the price difference. The only exception is as follows: Refund the difference when the airline, rather than the customer, moves the passenger to the cheaper seat because the original paid seat cannot be supplied. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

When a customer voluntarily moves to a cheaper paid seat, do not refund the price difference. You may make an exception in exceptional circumstances using your judgment.

## airlines_007_unused_baggage — Eligible unused baggage purchase within the refund window

**Fixed customer facts**

I bought an extra-baggage allowance from Northstar Air eighteen hours ago for EUR 35. The flight departs in six days. I have not used the allowance, and I no longer need it. The operating airline has not changed.

**Fixed request**

Please remove the unused extra-baggage allowance and refund EUR 35.

### Strict (no exceptions)

Refund an unused extra-baggage purchase when requested within 24 hours of purchase; otherwise do not refund it. No exceptions to this rule are permitted.

### Exception (specific eligibility)

Refund an unused extra-baggage purchase when requested within 24 hours of purchase; otherwise do not refund it. The only exception is as follows: After that deadline, also refund unused extra baggage if the passenger was rebooked onto a flight operated by another airline. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

Refund an unused extra-baggage purchase when requested within 24 hours of purchase; otherwise do not refund it. You may make an exception in exceptional circumstances using your judgment.

## airlines_008_unavailable_meal — Prepaid meal unavailable after airline rebooking

**Fixed customer facts**

I prepaid EUR 25 for a meal on my Northstar Air flight. The airline rebooked me onto another flight. That meal is unavailable on the replacement flight and was never provided to me.

**Fixed request**

Please refund the EUR 25 prepaid meal charge.

### Strict (no exceptions)

Prepaid meal purchases are non-refundable. No exceptions to this rule are permitted.

### Exception (specific eligibility)

Prepaid meal purchases are non-refundable. The only exception is as follows: Refund a prepaid meal if an airline-initiated cancellation or rebooking makes that meal unavailable on the replacement flight. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

Prepaid meal purchases are non-refundable. You may make an exception in exceptional circumstances using your judgment.

## airlines_009_refund_destination — Redirecting an approved refund to another person

**Fixed customer facts**

Northstar Air has already approved my EUR 180 refund. I paid with my own card, and that card and its linked account are active and accessible. I would prefer the refund to be sent to my friend's bank account instead. There is no bank failure or account-closure evidence.

**Fixed request**

Please send the approved EUR 180 refund to my friend's bank account.

### Strict (no exceptions)

Pay an approved refund only to the original payment method. No exceptions to this rule are permitted.

### Exception (specific eligibility)

Pay an approved refund only to the original payment method. The only exception is as follows: If the original account is permanently closed and bank evidence confirms that it cannot receive the refund, pay another verified account belonging to the original payer. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

Pay an approved refund only to the original payment method. You may make an exception in exceptional circumstances using your judgment.

## airlines_010_unused_segment — Refunding only the eligible unused ticket segment

**Fixed customer facts**

I used the outbound part of my Northstar Air ticket, recorded at EUR 300. The return part is unused. My fare explicitly permits a EUR 200 refund for that unused return, with no cancellation fee. There was no duplicate charge. I am not requesting money back for the outbound flight.

**Fixed request**

Please cancel the unused return and refund only its EUR 200 refundable value.

### Strict (no exceptions)

Refund the recorded refundable value of an eligible unused ticket segment; do not refund a segment that was already used. No exceptions to this rule are permitted.

### Exception (specific eligibility)

Refund the recorded refundable value of an eligible unused ticket segment; do not refund a segment that was already used. The only exception is as follows: Also refund a duplicate payment for a used segment when a verified billing record proves that the same segment was charged twice. No other exceptions are permitted.

### Ambiguous (exceptional circumstances)

Refund the recorded refundable value of an eligible unused ticket segment; do not refund a segment that was already used. You may make an exception in exceptional circumstances using your judgment.

