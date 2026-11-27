
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta




class IrConf(models.Model):
    _inherit = 'ir.config_parameter'



    def write(self, values):
        print(1111111111111111111111111111111111,values)
        if self.key == 'database.expiration_date':
            print(999999999999999999999999)
            infin_date = fields.Date.today() + relativedelta(years=99)
            values['value'] = infin_date
        return super(IrConf, self).write(values)


    @api.model_create_multi
    def create(self, vals_list):
        # Add code here
        for values in vals_list:
            if values.get('key',False) == 'database.expiration_date':
                print(7777777777777777777777777777777777777)
                infin_date = fields.Date.today() + relativedelta(years=99)
                values['value'] = infin_date
        return super(IrConf, self).create(values)





class AvtivDb(models.Model):
    _name = 'activate.enterprise.db'
    _description = 'Avtivate Enterprise Db'




    @api.model
    def set_infinity_expiration_date_db(self):
        self =  self.sudo()
        print(9999966666666666666666666666666666666666)
        value = fields.Date.today() + relativedelta(years=99)
        exp_param = self.env['ir.config_parameter'].search([('key','=','database.expiration_date')],limit=1)
        if not exp_param.id:
            exp_param = self.env['ir.config_parameter'].create({
                'key':'database.expiration_date',
                'value':value,
            })
        else:
            exp_param.value = fields.Date.today() + relativedelta(years=99)







