BOUNCED_LABEL_AR = 'مرتد'


def post_init_hook(env):
    _set_bounced_label(env)
    _migrate_manual_fields(env)


def _set_bounced_label(env):
    """Show the native 'rejected' payment state as 'مرتد' in Arabic."""
    selection = env['ir.model.fields.selection'].search([
        ('field_id.model', '=', 'account.payment'),
        ('field_id.name', '=', 'state'),
        ('value', '=', 'rejected'),
    ])
    if not selection:
        return
    for lang in env['res.lang'].search([('code', '=like', 'ar%')]):
        selection.with_context(lang=lang.code).name = BOUNCED_LABEL_AR


def _migrate_manual_fields(env):
    """Copy data from the old manual (Studio/dev-mode) fields if they exist."""
    cr = env.cr
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'account_payment'
          AND column_name IN ('x_is_check', 'x_deposit_account_id', 'x_deposit_move_id')
    """)
    cols = {row[0] for row in cr.fetchall()}
    if 'x_is_check' in cols:
        cr.execute("UPDATE account_payment SET is_cheque = TRUE WHERE x_is_check IS TRUE")
    if 'x_deposit_account_id' in cols:
        cr.execute("""
            UPDATE account_payment SET cheque_deposit_account_id = x_deposit_account_id
            WHERE x_deposit_account_id IS NOT NULL
        """)
    if 'x_deposit_move_id' in cols:
        cr.execute("""
            UPDATE account_payment SET cheque_deposit_move_id = x_deposit_move_id
            WHERE x_deposit_move_id IS NOT NULL
        """)
    env['account.payment'].invalidate_model()
