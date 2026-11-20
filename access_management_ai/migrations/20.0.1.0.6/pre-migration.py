# Copyright (C) NexGen Solutions
"""Move this module's pre-20 security metadata to Odoo 20's ir.access.

Odoo 20 replaced both ``ir.rule`` and ``ir.model.access`` with ``ir.access``.
Core's database upgrade handles standard records, while this migration keeps
the module-owned external IDs valid before the upgraded XML and CSV data is
loaded.  It is deliberately idempotent: a database already converted by an
Odoo/OpenUpgrade base migration simply has no legacy XML IDs to process.
"""


MODULE = 'access_management_ai'


def _table_exists(cr, table_name):
    cr.execute('SELECT to_regclass(%s)', (table_name,))
    return bool(cr.fetchone()[0])


def _move_legacy_acl(cr):
    if not _table_exists(cr, 'ir_model_access'):
        return
    cr.execute(
        """
        SELECT data.id, data.res_id, acl.name, acl.active, acl.model_id,
               acl.group_id, acl.perm_read, acl.perm_write,
               acl.perm_create, acl.perm_unlink
          FROM ir_model_data AS data
          JOIN ir_model_access AS acl ON acl.id = data.res_id
         WHERE data.module = %s AND data.model = 'ir.model.access'
        """,
        (MODULE,),
    )
    for xmlid_id, legacy_id, name, active, model_id, group_id, can_read, can_write, can_create, can_unlink in cr.fetchall():
        operation = ''.join((
            'c' if can_create else '',
            'r' if can_read else '',
            'u' if can_write else '',
            'd' if can_unlink else '',
        ))
        if not operation:
            # Odoo 20 requires an operation.  An ACL granting nothing never
            # had an effect, so discard its obsolete external ID safely.
            cr.execute('DELETE FROM ir_model_data WHERE id = %s', (xmlid_id,))
            continue
        cr.execute(
            """
            INSERT INTO ir_access
                (name, active, model_id, group_id, operation, domain,
                 create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, %s, %s, NULL, 1, 1,
                    NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
            RETURNING id
            """,
            (name, active, model_id, group_id, operation),
        )
        access_id = cr.fetchone()[0]
        cr.execute(
            "UPDATE ir_model_data SET model = 'ir.access', res_id = %s WHERE id = %s",
            (access_id, xmlid_id),
        )
        cr.execute('DELETE FROM ir_model_access WHERE id = %s', (legacy_id,))


def _move_legacy_rule(cr):
    if not _table_exists(cr, 'ir_rule'):
        return
    cr.execute(
        """
        SELECT data.id, data.res_id, rule.name, rule.active, rule.model_id,
               rule.domain_force, rule.perm_read, rule.perm_write,
               rule.perm_create, rule.perm_unlink
          FROM ir_model_data AS data
          JOIN ir_rule AS rule ON rule.id = data.res_id
         WHERE data.module = %s AND data.model = 'ir.rule'
        """,
        (MODULE,),
    )
    for xmlid_id, legacy_id, name, active, model_id, domain, can_read, can_write, can_create, can_unlink in cr.fetchall():
        operation = ''.join((
            'c' if can_create else '',
            'r' if can_read else '',
            'u' if can_write else '',
            'd' if can_unlink else '',
        )) or 'crud'
        cr.execute(
            """
            INSERT INTO ir_access
                (name, active, model_id, group_id, operation, domain,
                 create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, NULL, %s, %s, 1, 1,
                    NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
            RETURNING id
            """,
            (name, active, model_id, operation, domain),
        )
        access_id = cr.fetchone()[0]
        cr.execute(
            "UPDATE ir_model_data SET model = 'ir.access', res_id = %s WHERE id = %s",
            (access_id, xmlid_id),
        )
        cr.execute('DELETE FROM ir_rule WHERE id = %s', (legacy_id,))


def migrate(cr, version):
    if not version or not _table_exists(cr, 'ir_access'):
        return
    _move_legacy_acl(cr)
    _move_legacy_rule(cr)
