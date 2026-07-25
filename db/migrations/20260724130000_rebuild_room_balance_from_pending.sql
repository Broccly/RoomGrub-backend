-- migrate:up

-- Wipe and rebuild SpendingSplits/RoomBalanceSummary from scratch, covering
-- only pending (unsettled) Spendings — settled expenses don't affect
-- pending_amount so there's no need to materialize splits for them.
--
-- Unlike the 20260722120000 backfill, the participant set here is current
-- UserRooms members UNION the expense's actual payer (Spendings.user_id).
-- That UNION is what fixes the bug: previously, if a payer had left the
-- room, they were dropped from the join entirely and no split row ever
-- carried their amount_paid, leaving that expense's money uncredited.

DELETE FROM public."RoomBalanceSummary";
DELETE FROM public."SpendingSplits";

WITH pending_spendings AS (
    SELECT id, room, user_id AS payer_id, money, created_at
    FROM public."Spendings"
    WHERE settled_at IS NULL AND (settled IS NULL OR settled = false)
),
participants AS (
    SELECT ps.id AS spending_id, ur.user_id AS participant_id
    FROM pending_spendings ps
    JOIN public."UserRooms" ur ON ur.room_id = ps.room
    UNION
    SELECT ps.id, ps.payer_id
    FROM pending_spendings ps
),
counted AS (
    SELECT spending_id, COUNT(*) AS participant_count
    FROM participants
    GROUP BY spending_id
)
INSERT INTO public."SpendingSplits" (spending_id, user_id, amount_paid, amount_owed, created_at)
SELECT
    p.spending_id,
    p.participant_id,
    CASE WHEN p.participant_id = ps.payer_id THEN ps.money ELSE 0 END,
    ROUND(ps.money::numeric / c.participant_count, 2),
    ps.created_at
FROM participants p
JOIN pending_spendings ps ON ps.id = p.spending_id
JOIN counted c ON c.spending_id = p.spending_id;

WITH net AS (
    SELECT s.room AS room_id, ss.user_id, SUM(ss.amount_paid - ss.amount_owed) AS pending_amount
    FROM public."SpendingSplits" ss
    JOIN public."Spendings" s ON s.id = ss.spending_id
    GROUP BY s.room, ss.user_id
)
INSERT INTO public."RoomBalanceSummary" (room_id, user_id, pending_amount, settled_at, updated_at)
SELECT
    ur.room_id,
    ur.user_id,
    COALESCE(net.pending_amount, 0),
    NULL::timestamptz,
    now()
FROM public."UserRooms" ur
LEFT JOIN net ON net.room_id = ur.room_id AND net.user_id = ur.user_id
UNION
SELECT
    net.room_id,
    net.user_id,
    net.pending_amount,
    NULL::timestamptz,
    now()
FROM net
LEFT JOIN public."UserRooms" ur ON ur.room_id = net.room_id AND ur.user_id = net.user_id
WHERE ur.user_id IS NULL;

-- migrate:down

DELETE FROM public."RoomBalanceSummary";
DELETE FROM public."SpendingSplits";
