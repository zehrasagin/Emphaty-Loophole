# Scenario catalog

| ID | Decision problem | Source provider | Strict | Exception | Ambiguous |
| --- | --- | --- | --- | --- | --- |
| airlines_001_no_show | Refund after voluntary non-travel | Ryanair | decline_requested_action | decline_requested_action | discretionary_review |
| airlines_002_bereavement_window | Bereavement outside a defined window | Ryanair | decline_requested_action | decline_requested_action | discretionary_review |
| airlines_003_early_cancellation | Early cancellation with an administrative deduction | easyJet | decline_requested_action | approve_requested_action | discretionary_review |
| airlines_004_change_fee | Waiving a voluntary flight-change fee | easyJet | decline_requested_action | decline_requested_action | discretionary_review |
| airlines_005_near_departure_cancellation | Booking-error cancellation close to departure | British Airways | decline_requested_action | decline_requested_action | discretionary_review |
| airlines_006_cheaper_seat | Price difference after voluntarily moving to a cheaper seat | British Airways | decline_requested_action | decline_requested_action | discretionary_review |
| airlines_007_unused_baggage | Eligible unused baggage purchase within the refund window | KLM | approve_requested_action | approve_requested_action | approve_requested_action |
| airlines_008_unavailable_meal | Prepaid meal unavailable after airline rebooking | KLM | decline_requested_action | approve_requested_action | discretionary_review |
| airlines_009_refund_destination | Redirecting an approved refund to another person | Lufthansa | decline_requested_action | decline_requested_action | discretionary_review |
| airlines_010_unused_segment | Refunding only the eligible unused ticket segment | Lufthansa | approve_requested_action | approve_requested_action | approve_requested_action |
