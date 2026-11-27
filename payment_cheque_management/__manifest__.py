{
    'name': 'Cheque Management on Payments',
    'version': '20.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Cheque flag, deposit and bounce actions on customer/vendor payments',
    'description': """
Adds to account.payment:
- "Cheque" checkbox that auto-selects the cheque payment method
- Deposit action: posts Dr deposit account / Cr outstanding (cheques under collection)
  and reconciles it, moving the payment to Reconciled
- Bounce action: unreconciles and deletes the payment entry, sets state to Rejected (shown as "مرتد")
- Reset to draft also deletes the deposit entry
- Shows Company Bank Account on paid cheque payments
""",
    'depends': ['account'],
    'data': [
        'views/account_payment_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
