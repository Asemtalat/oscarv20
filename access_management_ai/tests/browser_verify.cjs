/* Run with AM20_URL/AM20_DB against an isolated verification database only. */
const puppeteer = require(process.env.AM20_PUPPETEER || '/home/synconics/.npm/_npx/55158e48eb5c59f7/node_modules/puppeteer');
const assert = require('node:assert/strict');
const base = process.env.AM20_URL || 'http://127.0.0.1:2223';
const db = process.env.AM20_DB || 'am20_verify_20260917';
const artifacts = process.env.AM20_ARTIFACTS || '/tmp/access-management-v20-meIDcw';
if (db === 'v20_ent' && process.env.AM20_SMOKE_ONLY !== '1') {
    throw new Error('Fixture-based browser tests require an isolated database.');
}

(async () => {
    const browser = await puppeteer.launch({executablePath: '/usr/bin/google-chrome', headless: true,
        args: ['--no-sandbox', '--disable-dev-shm-usage'], defaultViewport: {width: 1440, height: 1000}});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => {
        if (message.type() === 'error') errors.push(message.text());
    });
    page.on('dialog', dialog => dialog.accept());
    try {
        await page.goto(`${base}/web/login?db=${db}&debug=assets`, {waitUntil: 'networkidle2', timeout: 120000});
        // The first asset build can hydrate and replace the login form. Wait
        // for its interactive submit button before entering credentials.
        await page.waitForSelector('.oe_login_form button[type=submit]', {visible: true, timeout: 60000});
        await page.type('input[name=login]', process.env.AM20_LOGIN || 'admin');
        await page.type('input[name=password]', process.env.AM20_PASSWORD || 'a');
        await Promise.all([page.waitForNavigation({waitUntil: 'networkidle2', timeout: 120000}), page.click('.oe_login_form button[type=submit]')]);
        await page.waitForSelector('.o_web_client', {timeout: 120000});
        await page.screenshot({path: `${artifacts}/admin-home.png`});
        console.log('LOGIN', page.url());
        const state = await page.evaluate(() => {
            const loader = odoo.loader;
            return {failed: [...loader.failed || []], modules: [...loader.modules.keys()].filter(k => k.startsWith('@access_management_ai/'))};
        });
        console.log('MODULES', JSON.stringify(state));
        assert.equal(state.modules.length, 15, 'all custom JS modules load');
        assert.equal(state.failed.length, 0, 'no JS module loader failures');
        if (process.env.AM20_SMOKE_ONLY === '1') {
            assert.deepEqual(errors, []);
            console.log('SMOKE_OK');
            return;
        }
        const fixture = await page.evaluate(async () => {
            const orm = odoo.__WOWL_DEBUG__.root.env.services.orm;
            const ref = async (name) => (await orm.searchRead('ir.model.data', [['module', '=', 'base'], ['name', '=', name]], ['res_id']))[0].res_id;
            const create = async (model, vals) => (await orm.create(model, [vals], {context: {
                no_reset_password: true, tracking_disable: true,
            }}))[0];
            const [partnerModel] = await orm.searchRead('ir.model', [['model', '=', 'res.partner']], ['id']);
            const userLogin = `am20_browser_${Date.now()}`;
            const userId = await create('res.users', {name: 'AM20 Browser User', login: userLogin,
                group_ids: [[6, 0, await Promise.all(['group_user', 'group_partner_manager', 'group_allow_export'].map(ref))]]});
            const ruleId = await create('access.management', {name: 'AM20 Browser Profile', user_ids: [[4, userId]],
                hide_systray_keys: 'mail.activity_menu'});
            const lineId = await create('access.management.model', {rule_id: ruleId, model_id: partnerModel.id,
                perm_create: false, perm_write: false, perm_unlink: false, allow_archive: false,
                allow_duplicate: false, allow_export: false, hide_import_button: true,
                hide_custom_filter: true, hide_custom_group: true, chatter_hide_send_message: true,
                chatter_hide_log_note: true, chatter_hide_activities: true, chatter_hide_followers: true,
                chatter_hide_attachments: true, chatter_hide_search: true});
            const elementId = await create('access.management.element', {rule_id: ruleId, model_id: partnerModel.id,
                element_type: 'page', element_ref: 'sales_purchases', view_type: 'form'});
            const partnerId = await create('res.partner', {name: 'AM20 Browser Contact'});
            const roleId = await create('access.role', {name: 'AM20 Browser Role'});
            const requestId = await create('access.request', {role_id: roleId, request_reason: 'AM20 Browser PDF'});
            await orm.call('ir.config_parameter', 'set_str', ['report.url', location.origin]);
            const reports = await orm.searchRead('ir.actions.report', [['report_name', 'like', 'access_management_ai.%']], ['report_name', 'model']);
            return {userId, userLogin, ruleId, lineId, elementId, partnerId, roleId, requestId, reports};
        });
        const openView = async (model, type, id) => {
            await page.evaluate(async ({model, type, id}) => {
                await odoo.__WOWL_DEBUG__.root.env.services.action.doAction({
                    type: 'ir.actions.act_window', name: `AM20 ${model}`, res_model: model,
                    res_id: id || false, views: [[false, type]], target: 'current',
                });
            }, {model, type, id});
            await page.waitForSelector(`.o_${type}_view`, {timeout: 30000});
            console.log('VIEW', model, type);
        };
        await openView('access.management', 'form', fixture.ruleId);
        const tabs = await page.$$eval('.o_notebook > .o_notebook_headers .nav-link', els => els.map(e => e.textContent.trim()));
        console.log('RULE_TABS', JSON.stringify(tabs));
        for (const label of tabs) {
            await page.evaluate(label => [...document.querySelectorAll('.o_notebook > .o_notebook_headers .nav-link')]
                .find(e => e.textContent.trim() === label)?.click(), label);
            await page.waitForFunction(label => [...document.querySelectorAll('.o_notebook .nav-link.active')]
                .some(e => e.textContent.trim() === label), {}, label);
        }
        await page.evaluate(() => [...document.querySelectorAll('.o_notebook .nav-link')].find(e => e.textContent.trim() === 'Model Access Rules').click());
        await page.waitForSelector('.o_field_widget[name="model_access_ids"] .o_data_row td.o_data_cell');
        await page.click('.o_field_widget[name="model_access_ids"] .o_data_row td.o_data_cell');
        await page.waitForSelector('.o_dialog .o_form_view');
        console.log('MODEL_TABS', await page.$$eval('.o_notebook .nav-link', els => els.map(e => e.textContent.trim())));
        await page.evaluate(() => [...document.querySelectorAll('.o_notebook .nav-link')].find(e => /search/i.test(e.textContent))?.click());
        await page.waitForSelector('.am-search-items-selector button', {timeout: 30000});
        await page.click('.am-search-items-selector button');
        await page.click('.o_dialog .modal-footer .btn-primary');
        await page.waitForSelector('.o_dialog', {hidden: true});
        await Promise.all([page.waitForResponse(r => r.url().includes('/web_save') && r.ok()), page.click('.o_form_button_save')]);
        await page.evaluate(() => [...document.querySelectorAll('.o_notebook .nav-link')].find(e => e.textContent.trim() === 'Hide UI Elements').click());
        await page.waitForSelector('.o_field_widget[name="element_access_ids"] .o_data_row td.o_data_cell');
        await page.click('.o_field_widget[name="element_access_ids"] .o_data_row td.o_data_cell');
        await page.waitForFunction(() => document.querySelectorAll('.o_field_dynamic_element_selection select option').length > 1);
        await page.screenshot({path: `${artifacts}/element-selector.png`});
        await page.click('.o_dialog .modal-footer .btn-secondary');
        await page.waitForSelector('.o_dialog', {hidden: true});
        const views = [
            ['access.management', 'kanban'], ['access.management', 'list'],
            ['access.role', 'kanban'], ['access.role', 'form'],
            ['access.management.group', 'kanban'], ['access.management.group', 'form'],
            ['access.login.log', 'list'], ['access.audit.log', 'list'],
            ['access.request', 'list'], ['access.request', 'kanban'], ['access.request', 'calendar'],
            ['access.request', 'pivot'], ['access.request', 'graph'],
            ['access.management.report', 'pivot'], ['access.management.report', 'graph'], ['access.management.report', 'kanban'],
            ['access.import.export', 'form'], ['access.management.transfer', 'form'], ['access.group.assign', 'form'],
            ['access.rule.ai.wizard', 'form'], ['access.role.ai.wizard', 'form'],
            ['res.config.settings', 'form'],
        ];
        for (const [model, type] of views) await openView(model, type);
        const reportIds = {'access.management': fixture.ruleId, 'access.role': fixture.roleId, 'access.request': fixture.requestId};
        for (const report of fixture.reports) {
            const pdf = await page.evaluate(async ({name, id}) => {
                const response = await fetch(`/report/pdf/${name}/${id}`);
                const data = new Uint8Array(await response.arrayBuffer());
                return {status: response.status, length: data.length, header: new TextDecoder().decode(data.slice(0, 5))};
            }, {name: report.report_name, id: reportIds[report.model]});
            assert.equal(pdf.status, 200);
            assert.equal(pdf.header, '%PDF-');
            assert.ok(pdf.length > 1000);
            console.log('PDF', report.report_name, pdf.length);
        }
        await page.click('.o_am_switch_user_btn');
        await page.waitForSelector('.o_am_switch_user_dropdown input');
        await page.type('.o_am_switch_user_dropdown input', fixture.userLogin);
        await page.waitForFunction(login => [...document.querySelectorAll('.o_am_switch_user_item')]
            .some(e => e.textContent.includes(login)), {}, fixture.userLogin);
        await Promise.all([
            page.waitForNavigation({waitUntil: 'networkidle2', timeout: 120000}),
            page.evaluate(login => [...document.querySelectorAll('.o_am_switch_user_item')].find(e => e.textContent.includes(login)).click(), fixture.userLogin),
        ]);
        await page.waitForSelector('.o_web_client');
        const switched = await page.evaluate(() => odoo.loader.modules.get('@web/session').session.access_management_ai);
        assert.equal(await page.evaluate(() => odoo.loader.modules.get('@web/core/user').user.userId), fixture.userId);
        assert.equal(switched.switch_from.id > 0, true, 'original admin retained after sync');
        assert.equal(switched.can_switch_user, true);
        await openView('res.partner', 'form', fixture.partnerId);
        await page.waitForSelector('.o-mail-Chatter');
        await page.waitForFunction(() => document.querySelector('.o-mail-Chatter').classList.contains('o-am-hide-send-message'));
        assert.equal(await page.$eval('.o-mail-Chatter-sendMessage', el => getComputedStyle(el).display), 'none');
        assert.equal(await page.$eval('.o-mail-Chatter-logNote', el => getComputedStyle(el).display), 'none');
        await page.screenshot({path: `${artifacts}/restricted-contact.png`});
        await openView('res.partner', 'list');
        assert.equal(await page.$('.o_list_button_add'), null, 'Create removed');
        await page.click('.o_searchview_dropdown_toggler');
        await page.waitForSelector('.o_search_bar_menu');
        assert.equal(await page.$('.o_search_bar_menu .o_add_custom_filter'), null, 'Custom filter removed');
        await page.keyboard.press('Escape');
        await page.waitForSelector('.o_data_row .o_list_record_selector', {visible: true});
        await page.click('.o_data_row .o_list_record_selector');
        const actionButton = await page.$('button[aria-label="Actions menu"]');
        if (actionButton) {
            await actionButton.click();
            await page.waitForSelector('.o-dropdown--menu');
            const labels = await page.$$eval('.o-dropdown--menu .o_menu_item', els => els.map(e => e.textContent.trim()));
            assert.ok(!labels.some(label => /^(Archive|Unarchive|Export|Delete)\b/i.test(label)), JSON.stringify(labels));
            await page.keyboard.press('Escape');
        }
        await page.click('.o_am_switch_user_btn');
        await page.waitForSelector('.o_am_switch_user_panel .btn-warning');
        await Promise.all([page.waitForNavigation({waitUntil: 'networkidle2', timeout: 120000}),
            page.click('.o_am_switch_user_panel .btn-warning')]);
        const restored = await page.evaluate(() => odoo.loader.modules.get('@web/session').session.access_management_ai);
        assert.equal(restored.is_access_admin, true);
        assert.equal(Boolean(restored.switch_from), false);
        console.log('SWITCH_BACK_OK');
        console.log('ERRORS', JSON.stringify(errors));
        assert.deepEqual(errors, []);
    } catch (error) {
        await page.screenshot({path: `${artifacts}/browser-failure.png`}).catch(() => {});
        console.error('FAIL', error.stack, 'BROWSER_ERRORS', errors);
        process.exitCode = 1;
    } finally {
        await browser.close();
    }
})();
