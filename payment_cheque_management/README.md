# payment_cheque_management (Odoo 20)

## Install
1. Copy the `payment_cheque_management` folder into the server addons path (and commit it to git).
2. Restart Odoo, Apps > Update Apps List, search "Cheque Management on Payments", Install.

## Requirements
- A payment method line whose name contains "شيك" on each journal used for cheques.
- Its Outstanding Receipts/Payments account = cheques under collection (e.g. 120801).

## Migrating a database that has the manual (dev-mode) version
Install the module FIRST (its post-init hook copies x_is_check / x_deposit_account_id /
x_deposit_move_id into the new fields), then remove the manual records, in this order:
1. Settings > Technical > Views: delete the 4 views named `account.payment.form.check*`
   (company_bank, draft, deposit, then the base one).
2. Settings > Technical > Automation Rules: delete "شيك: اختيار طريقة الدفع شيك".
3. Settings > Technical > Server Actions: delete "شيك مرتد", "إيداع شيك",
   "إعادة تعيين كمسودة مع مسح قيد الإيداع", "اختيار طريقة دفع شيك".
4. Settings > Technical > Fields (account.payment): delete x_is_check,
   x_deposit_account_id, x_deposit_move_id.
5. Studio: remove any customization hiding "Company Bank Account" on paid payments.

## Notes
- Upgrading `account` may reset the Arabic label of state "rejected" back to "تم الرفض";
  reinstalling/upgrading this module re-applies only on install (post_init_hook), so
  re-set it from Technical > Fields > state > selection if needed.
- Deposit entry date = today. Bank statement lines must be matched against the deposit entry.
