# -*- coding: utf-8 -*-
"""Odoo 19 removed ``hr.contract`` (contract data moved to ``hr.version``).

Before the ORM updates this module:
* keep a copy of the attendance settings that were stored on the contract
  (only possible if the ``hr_contract`` table still exists at this point);
* detach ``attendance_sheet.contract_id`` (it referenced the removed model);
  it is re-linked to a version in the post-migration script.
"""


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return

    cr.execute("SELECT to_regclass('hr_contract')")
    if cr.fetchone()[0]:
        policy = 'att_policy_id' if _column_exists(cr, 'hr_contract', 'att_policy_id') else 'NULL::integer'
        auto = ('auto_attendance_sheet'
                if _column_exists(cr, 'hr_contract', 'auto_attendance_sheet') else 'NULL::boolean')
        cr.execute("DROP TABLE IF EXISTS rm_att_contract_backup")
        cr.execute(f"""
            CREATE TABLE rm_att_contract_backup AS
            SELECT id, employee_id, date_start,
                   {policy} AS att_policy_id, {auto} AS auto_attendance_sheet
              FROM hr_contract
        """)

    if _column_exists(cr, 'attendance_sheet', 'contract_id') \
            and not _column_exists(cr, 'attendance_sheet', 'old_contract_id'):
        cr.execute("""
            ALTER TABLE attendance_sheet
            DROP CONSTRAINT IF EXISTS attendance_sheet_contract_id_fkey
        """)
        cr.execute("ALTER TABLE attendance_sheet RENAME COLUMN contract_id TO old_contract_id")
