# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class HrLoan(models.Model):
    """Model for Loan Requests for employees."""
    _name = 'hr.loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Loan Request"

    @api.model
    def default_get(self, field_list):
        """ Retrieve default values for specified fields. """
        result = super(HrLoan, self).default_get(field_list)
        if result.get('user_id'):
            ts_user_id = result['user_id']
        else:
            ts_user_id = self.env.context.get('user_id', self.env.user.id)
        result['employee_id'] = self.env['hr.employee'].search(
            [('user_id', '=', ts_user_id)], limit=1).id
        return result

    def _compute_loan_amount(self):
        """ calculate the total amount paid towards the loan. """
        total_paid = 0.0
        for loan in self:
            for line in loan.loan_line_ids:
                if line.paid:
                    total_paid += line.amount
            balance_amount = loan.loan_amount - total_paid
            loan.total_amount = loan.loan_amount
            loan.balance_amount = balance_amount
            loan.total_paid_amount = total_paid

    name = fields.Char(string="Loan Name", default="/", readonly=True,
                       help="Name of the loan")
    date = fields.Date(string="Date", default=fields.Date.today,
                       readonly=True, help="Date")
    employee_id = fields.Many2one(comodel_name='hr.employee', string="Employee",
                                  required=True, help="Employee")
    department_id = fields.Many2one(comodel_name='hr.department',
                                    related="employee_id.department_id",
                                    readonly=True,
                                    string="Department", help="Employee")
    installment = fields.Integer(string="No Of Installments", default=1,
                                 help="Number of installments")
    payment_date = fields.Date(string="Payment Start Date", required=True,
                               default=fields.Date.today,
                               help="Date of the payment")
    loan_line_ids = fields.One2many(comodel_name='hr.loan.line',
                                    help="Loan lines",
                                    inverse_name='loan_id', string="Loan Line",
                                    index=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 help="Company",
                                 default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one(comodel_name='res.currency',
                                  string='Currency', required=True,
                                  help="Currency",
                                  default=lambda self:
                                  self.env.user.company_id.currency_id)
    job_position_id = fields.Many2one(comodel_name='hr.job',
                                      related="employee_id.job_id",
                                      readonly=True, string="Job Position",
                                      help="Job position")
    loan_amount = fields.Float(string="Loan Amount", required=True,
                               help="Loan amount")
    total_amount = fields.Float(string="Total Amount", store=True,
                                readonly=True, compute='_compute_loan_amount',
                                help="Total loan amount")
    balance_amount = fields.Float(string="Balance Amount", store=True,
                                  compute='_compute_loan_amount',
                                  help="Balance amount")
    total_paid_amount = fields.Float(string="Total Paid Amount", store=True,
                                     compute='_compute_loan_amount',
                                     help="Total paid amount")
    state = fields.Selection([
        ('draft', 'Draft'), ('waiting_approval_1', 'Submitted'),
        ('approve', 'Approved'), ('refuse', 'Refused'), ('cancel', 'Canceled'),
    ], string="State", help="states of loan request", default='draft',
        tracking=True, copy=False, )
    
    
    payment_id = fields.Many2one(
        comodel_name='account.payment',
        string='Payment_id',
        required=False)
    @api.model_create_multi
    def create(self, vals_list):
        """creates new HR loan records with the provided values."""
        for values in vals_list:
            values['name'] = self.env['ir.sequence'].next_by_code('hr.loan.seq') or ' '
        return super().create(vals_list)

    def action_compute_installment(self):
        """This automatically create the installment the employee need to pay
        to company based on payment start date and the no of installments."""
        for loan in self:
            loan.loan_line_ids.unlink()
            date_start = datetime.strptime(str(loan.payment_date), '%Y-%m-%d')
            amount = loan.loan_amount / loan.installment
            for i in range(1, loan.installment + 1):
                self.env['hr.loan.line'].create({
                    'date': date_start,
                    'amount': amount,
                    'employee_id': loan.employee_id.id,
                    'loan_id': loan.id})
                date_start = date_start + relativedelta(months=1)
            loan._compute_loan_amount()
        return True

    def action_refuse(self):
        """Action to refuse the loan"""
        return self.write({'state': 'refuse'})

    def action_submit(self):
        """Action to submit the loan"""
        self.write({'state': 'waiting_approval_1'})

    def action_cancel(self):
        """Action to cancel the loan"""
        self.write({'state': 'cancel'})

    def action_approve(self):
        """Approve loan by the manager"""
        for data in self:
            payment_model = self.env['account.payment']

            if not data.loan_line_ids:
                raise ValidationError(_("Please Compute installment"))
            else:
                # for loan_line in data.loan_line_ids:
                payment = payment_model.create({
                    'date': data.date,
                    'payment_type': 'outbound',  # Indicates a 'Send' payment
                    'partner_type': 'supplier',
                    'partner_id': (data.employee_id.work_contact_id or data.employee_id.user_id.partner_id).id,
                    'amount': data.loan_amount,
                    'journal_id': self.env['account.journal'].search([('type','=','cash')], limit=1).id,  # Default journal
                    # 'loan_line_id': loan_line.id,  # Custom field linking payment to loan line
                    'loan_id': data.id,  # Custom field linking payment to loan line
                })
                data.payment_id = payment.id
                data.write({'state': 'approve'})

    def unlink(self):
        """Unlink loan lines"""
        for loan in self:
            if loan.state not in ('draft', 'cancel'):
                raise UserError(
                    'You cannot delete a loan which is not in draft or '
                    'cancelled state')
        return super(HrLoan, self).unlink()


    payment_count = fields.Integer(
        string='Payment Count',
        compute='_compute_payment_count'
    )

    @api.depends('payment_id')
    def _compute_payment_count(self):
        for loan in self:
            loan.payment_count = 1 if loan.payment_id else 0

    def action_view_payment(self):
        """Action to view the Payment linked to this Picking."""
        self.ensure_one()
        if self.payment_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Payment',
                'res_model': 'account.payment',
                'view_mode': 'form',
                'res_id': self.payment_id.id,
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Payments',
                'res_model': 'account.payment',
                'view_mode': 'list,form',
                'domain': [('loan_id', '=', self.id)],
                'target': 'current',
            }
