-- migrate:up

-- Supabase dev and a database built from these migrations differ: Supabase still has
-- the legacy "Rooms".members / budget / admin and "Users".role columns and lacks
-- "Rooms".name, the migrations have the opposite. Every statement below is written
-- with IF [NOT] EXISTS so it applies cleanly to both.

-- Users: account type for the guest phases (docs/GUEST_ACCESS.md).
ALTER TABLE public."Users" ADD COLUMN IF NOT EXISTS type text DEFAULT 'registered' NOT NULL;
ALTER TABLE public."Users" ADD CONSTRAINT "Users_type_check"
    CHECK (type = ANY (ARRAY['registered'::text, 'guest'::text, 'placeholder'::text]));

-- Users: email becomes optional; guests and placeholders have none.
ALTER TABLE public."Users" ALTER COLUMN email DROP NOT NULL, ALTER COLUMN email DROP DEFAULT;
UPDATE public."Users" SET email = NULL WHERE email = '';

-- Users: several users may pick the same avatar.
ALTER TABLE public."Users" DROP CONSTRAINT IF EXISTS "Users_profile_key";

-- Users: uid is a stable id generated once at creation, no longer "<provider>:<email>".
UPDATE public."Users" SET uid = gen_random_uuid()::text;
ALTER TABLE public."Users"
    ALTER COLUMN uid SET DEFAULT gen_random_uuid()::text,
    ALTER COLUMN uid SET NOT NULL;

-- Users: drop the legacy global role. Room roles live in "UserRooms".role. These two
-- Supabase RLS policies read it (the backend bypasses RLS), so they go first.
DROP POLICY IF EXISTS admin_can_delete ON public."Spendings";
DROP POLICY IF EXISTS admin_can_update ON public."Spendings";
ALTER TABLE public."Users" DROP COLUMN IF EXISTS role;

-- Rooms: name, and drop the legacy stored columns (members and admin are derived from
-- "UserRooms"). Dropping admin also drops "Rooms_admin_fkey".
ALTER TABLE public."Rooms" ADD COLUMN IF NOT EXISTS name text;
ALTER TABLE public."Rooms"
    DROP COLUMN IF EXISTS members,
    DROP COLUMN IF EXISTS budget,
    DROP COLUMN IF EXISTS admin;

-- Rooms: uid generated once at creation.
UPDATE public."Rooms" SET uid = gen_random_uuid()::text;
ALTER TABLE public."Rooms"
    ALTER COLUMN uid SET DEFAULT gen_random_uuid()::text,
    ALTER COLUMN uid SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS "Rooms_uid_key" ON public."Rooms" USING btree (uid);

-- Spendings: the legacy payer email is optional; the payer is Spendings.user_id.
ALTER TABLE public."Spendings" ALTER COLUMN "user" DROP NOT NULL;

-- migrate:down

-- Not a full restore: the dropped legacy columns ("Rooms".members / budget / admin,
-- "Users".role) and the two RLS policies were never part of these migrations and are not
-- recreated, old uid values are not recovered, and "Rooms".name stays (it is in the baseline).

-- Fails if an expense has no payer email (e.g. one paid by a guest).
ALTER TABLE public."Spendings" ALTER COLUMN "user" SET NOT NULL;

DROP INDEX IF EXISTS public."Rooms_uid_key";
ALTER TABLE public."Rooms"
    ALTER COLUMN uid DROP NOT NULL,
    ALTER COLUMN uid DROP DEFAULT;

ALTER TABLE public."Users"
    ALTER COLUMN uid DROP NOT NULL,
    ALTER COLUMN uid DROP DEFAULT;

-- Fails if two users now share an avatar.
ALTER TABLE public."Users" ADD CONSTRAINT "Users_profile_key" UNIQUE (profile);

-- Fails if more than one user has no email.
UPDATE public."Users" SET email = '' WHERE email IS NULL;
ALTER TABLE public."Users"
    ALTER COLUMN email SET DEFAULT ''::character varying,
    ALTER COLUMN email SET NOT NULL;

ALTER TABLE public."Users" DROP CONSTRAINT IF EXISTS "Users_type_check";
ALTER TABLE public."Users" DROP COLUMN IF EXISTS type;
