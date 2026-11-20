# -*- coding: utf-8 -*-
# Copyright (C) NexGen Solutions
import json
from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    if not version:
        return

    # Odoo 19 uses JSONB for translated fields. 
    # If a field was previously a varchar and is now translate=True, we must cast it to JSONB.
    # Convert 'name' column in 'access_management' to jsonb
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='access_management' AND column_name='name' AND data_type='character varying'
            ) THEN
                ALTER TABLE access_management ALTER COLUMN name TYPE jsonb USING jsonb_build_object('en_US', name);
            END IF;
        END $$;
    """)

    # Convert 'name' column in 'access_management_tag' to jsonb
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='access_management_tag' AND column_name='name' AND data_type='character varying'
            ) THEN
                ALTER TABLE access_management_tag ALTER COLUMN name TYPE jsonb USING jsonb_build_object('en_US', name);
            END IF;
        END $$;
    """)
