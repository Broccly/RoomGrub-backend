-- migrate:up

-- Settlement tracking moves onto Spendings itself; the balance table's only
-- remaining job was recording settlements (per-expense rows carry a
-- spending_id, lump-sum rows carry NULL and are intentionally discarded).

ALTER TABLE public."Spendings" ADD COLUMN user_id bigint;
ALTER TABLE public."Spendings" ADD COLUMN settled_at timestamp with time zone;

ALTER TABLE public."Spendings"
    ADD CONSTRAINT "Spendings_user_id_fkey" FOREIGN KEY (user_id) REFERENCES public."Users"(id);

-- Backfill user_id from the email held in "user" (NOT NULL, FK to Users(email),
-- so every row maps).
UPDATE public."Spendings" s
SET user_id = u.id
FROM public."Users" u
WHERE u.email = s."user";

-- Backfill settled_at from per-expense settlement rows. Expenses settled via
-- "settle all" had their balance rows deleted at settle time, so they keep
-- settled_at NULL (the settled boolean still marks them).
UPDATE public."Spendings" s
SET settled_at = b.first_settled
FROM (
    SELECT spending_id, MIN(created_at) AS first_settled
    FROM public.balance
    WHERE spending_id IS NOT NULL
    GROUP BY spending_id
) b
WHERE b.spending_id = s.id;

ALTER TABLE public."Spendings" ALTER COLUMN user_id SET NOT NULL;

CREATE INDEX idx_spendings_user_id ON public."Spendings" USING btree (user_id);

DROP TABLE public.balance;

-- migrate:down

-- Best-effort rollback: recreates balance and re-derives per-expense
-- settlement rows from settled_at. Lump-sum rows (spending_id IS NULL) were
-- discarded on the way up and are unrecoverable.

CREATE TABLE public.balance (
    id integer NOT NULL,
    room bigint NOT NULL,
    "user" character varying,
    amount double precision,
    status text,
    created_at timestamp with time zone DEFAULT (now() AT TIME ZONE 'utc'::text),
    spending_id integer
);

CREATE SEQUENCE public.balance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.balance_id_seq OWNED BY public.balance.id;
ALTER TABLE ONLY public.balance ALTER COLUMN id SET DEFAULT nextval('public.balance_id_seq'::regclass);

ALTER TABLE ONLY public.balance ADD CONSTRAINT balance_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.balance ADD CONSTRAINT balance_room_fkey FOREIGN KEY (room) REFERENCES public."Rooms"(id);
ALTER TABLE ONLY public.balance ADD CONSTRAINT balance_spending_id_fkey FOREIGN KEY (spending_id) REFERENCES public."Spendings"(id) ON DELETE SET NULL;
ALTER TABLE ONLY public.balance ADD CONSTRAINT balance_user_fkey FOREIGN KEY ("user") REFERENCES public."Users"(email);

INSERT INTO public.balance (room, "user", amount, status, created_at, spending_id)
SELECT room, "user", -money, 'debit', settled_at, id
FROM public."Spendings"
WHERE settled_at IS NOT NULL;

DROP INDEX public.idx_spendings_user_id;
ALTER TABLE public."Spendings" DROP CONSTRAINT "Spendings_user_id_fkey";
ALTER TABLE public."Spendings" DROP COLUMN user_id;
ALTER TABLE public."Spendings" DROP COLUMN settled_at;
