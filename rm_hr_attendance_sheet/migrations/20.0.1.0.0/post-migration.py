# -*- coding: utf-8 -*-
"""Re-attach the attendance data to the Odoo 20 ``hr.version`` records."""


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", (table,))
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    if not version:
        return

    # 1. Attendance policy / auto generation flag saved from the old contracts
    #    (matched on employee + contract start date).
    if _table_exists(cr, 'rm_att_contract_backup'):
        cr.execute("""
            UPDATE hr_version v
               SET att_policy_id = b.att_policy_id,
                   auto_attendance_sheet = COALESCE(b.auto_attendance_sheet, FALSE)
              FROM rm_att_contract_backup b
             WHERE v.employee_id = b.employee_id
               AND v.contract_date_start = b.date_start
               AND b.att_policy_id IS NOT NULL
        """)
        cr.execute("DROP TABLE rm_att_contract_backup")

    # 2. Fallback when the contract table was already gone: use the policy of
    #    the latest attendance sheet of the employee.
    cr.execute("""
        UPDATE hr_version v
           SET att_policy_id = s.att_policy_id
          FROM (SELECT DISTINCT ON (employee_id) employee_id, att_policy_id
                  FROM attendance_sheet
                 WHERE att_policy_id IS NOT NULL
                 ORDER BY employee_id, date_to DESC) s
         WHERE v.employee_id = s.employee_id
           AND v.att_policy_id IS NULL
           AND v.contract_date_start IS NOT NULL
    """)

    # 3. Link every sheet to the version in effect at the end of its period
    #    (or to the first version of the employee if none started yet).
    cr.execute("""
        UPDATE attendance_sheet s
           SET version_id = (
               SELECT v.id FROM hr_version v
                WHERE v.employee_id = s.employee_id
                  AND v.contract_date_start IS NOT NULL
                  AND v.date_version <= s.date_to
                ORDER BY v.date_version DESC LIMIT 1)
         WHERE s.version_id IS NULL
    """)
    cr.execute("""
        UPDATE attendance_sheet s
           SET version_id = (
               SELECT v.id FROM hr_version v
                WHERE v.employee_id = s.employee_id
                  AND v.contract_date_start IS NOT NULL
                ORDER BY v.date_version ASC LIMIT 1)
         WHERE s.version_id IS NULL
    """)

    cr.execute("ALTER TABLE attendance_sheet DROP COLUMN IF EXISTS old_contract_id")
