-- Migration: Add order totals denormalization columns
-- Run once against your database before deploying the new backend code.
-- Safe to run on an empty table or a populated table.

ALTER TABLE "order"
    ADD COLUMN IF NOT EXISTS total_weight_g    FLOAT,
    ADD COLUMN IF NOT EXISTS total_volume_cm3  FLOAT,
    ADD COLUMN IF NOT EXISTS total_item_count  INTEGER;

-- After this migration, run the backfill script:
--   cd Back_end && python -c "
--   from Delivery_app_BK import create_app
--   app = create_app()
--   with app.app_context():
--       from Back_end.scripts.backfill_order_totals import run
--       run()
--   "
