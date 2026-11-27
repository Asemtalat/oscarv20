# -*- coding: utf-8 -*-
{
    'name': "Activate My DB",



    'post_init_hook': 'activate_enterprise_db',
    'depends': ['base'],

    'data': [
        'data/activate_crone_action.xml',
    ],

}
