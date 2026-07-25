-- migrate:up

-- The 20260722120000 backfill for RoomBalanceSummary.pending_amount only
-- summed SpendingSplits for Spendings where `settled = false` explicitly,
-- missing legacy rows where `settled IS NULL` (unsettled, per the
-- `settled IS NULL OR settled = FALSE` convention used everywhere else,
-- e.g. app/models/expenses/expenses_model.py). This left pending_amount
-- at 0 for members whose expenses had settled = NULL. Recompute it.

UPDATE public."RoomBalanceSummary" rbs
SET pending_amount = COALESCE(net.pending_amount, 0),
    updated_at = now()
FROM (
    SELECT s.room AS room_id, ss.user_id, SUM(ss.amount_paid - ss.amount_owed) AS pending_amount
    FROM public."SpendingSplits" ss
    JOIN public."Spendings" s ON s.id = ss.spending_id
    WHERE s.settled_at IS NULL AND (s.settled IS NULL OR s.settled = false)
    GROUP BY s.room, ss.user_id
) net
WHERE rbs.room_id = net.room_id
  AND rbs.user_id = net.user_id
  AND rbs.settled_at IS NULL;

-- Rows with no matching unsettled splits (net.pending_amount would be NULL,
-- so they weren't touched by the UPDATE's FROM join) should be zeroed too.
UPDATE public."RoomBalanceSummary" rbs
SET pending_amount = 0,
    updated_at = now()
WHERE rbs.settled_at IS NULL
  AND NOT EXISTS (
    SELECT 1
    FROM public."SpendingSplits" ss
    JOIN public."Spendings" s ON s.id = ss.spending_id
    WHERE s.settled_at IS NULL
      AND (s.settled IS NULL OR s.settled = false)
      AND s.room = rbs.room_id
      AND ss.user_id = rbs.user_id
  );

-- migrate:down

-- No-op: reverting to the buggy backfill values is not meaningful.
