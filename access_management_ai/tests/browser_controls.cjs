/* Extra browser regressions. Only run against an isolated verification DB. */
const puppeteer = require(process.env.AM20_PUPPETEER || '/home/synconics/.npm/_npx/55158e48eb5c59f7/node_modules/puppeteer');
const assert = require('node:assert/strict');
const base = process.env.AM20_URL || 'http://127.0.0.1:2223';
const db = process.env.AM20_DB || 'am20_audit_20260918';
const artifacts = process.env.AM20_ARTIFACTS || '/tmp/am20-audit-20260918';
assert.notEqual(db, 'v20_ent', 'Use an isolated database');

(async () => {
    const browser = await puppeteer.launch({executablePath: '/usr/bin/google-chrome', headless: true,
        args: ['--no-sandbox', '--disable-dev-shm-usage'], defaultViewport: {width: 1440, height: 1000}});
    const admin = await browser.newPage();
    const context = await browser.createBrowserContext();
    const userPage = await context.newPage();
    const errors = [];
    userPage.on('console', message => {
        if (message.type() === 'error') console.error('BROWSER_CONSOLE', message.text());
    });
    for (const page of [admin, userPage]) page.on('pageerror', error => errors.push(String(error)));
    const rpc = (page, path, params) => page.evaluate(async ({path, params}) => {
        const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params, id: 1})});
        return response.json();
    }, {path, params});
    const call = async (page, model, method, args, kwargs = {}) => {
        const data = await rpc(page, `/web/dataset/call_kw/${model}/${method}`, {model, method, args, kwargs});
        if (data.error) throw new Error(JSON.stringify(data.error));
        return data.result;
    };
    const login = async page => {
        await page.goto(`${base}/web/login?db=${db}`, {waitUntil: 'domcontentloaded'});
        const auth = await rpc(page, '/web/session/authenticate', {db, login: 'admin', password: process.env.AM20_PASSWORD || 'a'});
        assert.ok(auth.result?.is_admin);
    };
    const load = async page => {
        await page.goto(`${base}/odoo?debug=assets`, {waitUntil: 'domcontentloaded'});
        await page.waitForFunction(() => Boolean(window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.menu), {timeout: 120000});
    };
    const open = async (type, id, viewId = false) => {
        await userPage.evaluate(async ({type, id, viewId}) => {
            try {
                await odoo.__WOWL_DEBUG__.root.env.services.action.doAction({type: 'ir.actions.act_window', name: 'Audit Contacts',
                    res_model: 'res.partner', res_id: id || false, views: [[viewId, type]], target: 'current'});
            } catch (error) {
                console.error(error.stack, error.cause?.stack);
                throw error;
            }
        }, {type, id, viewId});
        await userPage.waitForSelector(`.o_${type}_view`, {timeout: 30000});
    };
    try {
        await login(admin);
        const ref = async name => (await call(admin, 'ir.model.data', 'search_read', [[['module', '=', 'base'], ['name', '=', name]]], {fields: ['res_id']}))[0].res_id;
        const create = async (model, vals) => (await call(admin, model, 'create', [[vals]], {context: {tracking_disable: true, no_reset_password: true}}))[0];
        const userId = await create('res.users', {name: 'AM20 deep browser user', login: `am20_deep_${Date.now()}`,
            group_ids: [[6, 0, await Promise.all(['group_user', 'group_partner_manager', 'group_allow_export'].map(ref))]]});
        const profileId = await create('access.management', {name: 'AM20 deep browser profile', user_ids: [[4, userId]]});
        const modelId = (await call(admin, 'ir.model', 'search_read', [[['model', '=', 'res.partner']]], {fields: ['id']}))[0].id;
        const phoneId = (await call(admin, 'ir.model.fields', 'search_read', [[['model', '=', 'res.partner'], ['name', '=', 'phone']]], {fields: ['id']}))[0].id;
        const emailId = (await call(admin, 'ir.model.fields', 'search_read', [[['model', '=', 'res.partner'], ['name', '=', 'email']]], {fields: ['id']}))[0].id;
        await create('access.management.field', {rule_id: profileId, model_id: modelId, field_id: phoneId, is_readonly: true});
        await create('access.management.field', {rule_id: profileId, model_id: modelId, field_id: emailId,
            is_invisible: true, invisible_condition: "[('ref', '=', 'AM20_HIDE')]"});
        const conditionalViewId = await create('ir.ui.view', {name: 'AM20 missing condition field browser form',
            model: 'res.partner', type: 'form', priority: 99,
            arch: '<form><sheet><group><field name="name"/><field name="email"/><field name="phone"/></group></sheet></form>'});
        const personId = await create('res.partner', {name: 'AM20 deep person', email: 'person@example.invalid', phone: '111'});
        const companyId = await create('res.partner', {name: 'AM20 deep hidden contact', ref: 'AM20_HIDE', email: 'hidden@example.invalid'});
        await login(userPage);
        const switched = await rpc(userPage, `/access_management/login_as/${userId}`, {});
        assert.ok(!switched.error);
        await load(userPage);
        assert.equal(await call(userPage, 'res.partner', 'has_access', [[], 'create']), true);
        await open('form', personId, conditionalViewId);
        assert.equal(await userPage.$('.o_field_widget[name="phone"] input'), null, 'Phone is read-only');
        await userPage.waitForSelector('.o_field_widget[name="email"]', {visible: true});
        await open('form', companyId, conditionalViewId);
        await userPage.waitForFunction(() => ![...document.querySelectorAll('.o_field_widget[name="email"]')].some(el => el.getClientRects().length));
        console.log('CONDITIONAL_FIELDS_OK');

        await call(admin, 'access.management', 'write', [[profileId], {readonly: true}]);
        for (const operation of ['create', 'write', 'unlink']) {
            assert.equal(await call(userPage, 'res.partner', 'has_access', [[], operation]), false);
        }
        await load(userPage);
        await open('list');
        assert.equal(await userPage.$('.o_list_button_add'), null);
        await userPage.waitForSelector('.o_data_row .o_list_record_selector', {visible: true});
        await userPage.click('.o_data_row .o_list_record_selector');
        const actions = await userPage.$('button[aria-label="Actions menu"]');
        if (actions) {
            await actions.click();
            await userPage.waitForSelector('.o-dropdown--menu');
            const labels = await userPage.$$eval('.o-dropdown--menu', elements => elements.map(el => el.innerText).join('\n'));
            assert.ok(!/\b(Archive|Unarchive|Export|Delete|Duplicate)\b/.test(labels), labels);
            await userPage.keyboard.press('Escape');
        }
        await open('form', personId);
        assert.ok(await userPage.$('.o_form_readonly'));
        assert.equal(await userPage.$('.o_form_button_create'), null);
        await userPage.screenshot({path: `${artifacts}/deep-readonly.png`});
        console.log('READONLY_UI_AND_SERVER_OK');

        await call(admin, 'access.management', 'write', [[profileId], {readonly: false,
            global_hide_searchbar: true, global_hide_chatter: true}]);
        assert.equal(await call(userPage, 'res.partner', 'has_access', [[], 'create']), true);
        await load(userPage);
        await open('list');
        await userPage.waitForSelector('.o_searchview', {hidden: true});
        await open('form', personId);
        await userPage.waitForSelector('.o-mail-Chatter', {hidden: true});
        console.log('GLOBAL_SEARCH_CHATTER_OK');

        await call(admin, 'access.management', 'write', [[profileId], {global_hide_searchbar: false, global_hide_chatter: false}]);
        await load(userPage);
        await open('list');
        await userPage.waitForSelector('.o_list_button_add', {visible: true});
        await userPage.waitForSelector('.o_searchview', {visible: true});
        await open('form', personId);
        await userPage.waitForSelector('.o-mail-Chatter', {visible: true});
        const unauthorized = await rpc(userPage, '/access_management/login_as/2', {});
        assert.ok(unauthorized.error, 'A regular user cannot impersonate the administrator');
        console.log('RESTORE_AND_IMPERSONATION_GUARD_OK');
        assert.deepEqual(errors, []);
        console.log('DEEP_CONTROLS_OK');
    } catch (error) {
        console.error(error.stack, 'PAGE_ERRORS', errors);
        await userPage.screenshot({path: `${artifacts}/deep-controls-failure.png`}).catch(() => {});
        process.exitCode = 1;
    } finally {
        await browser.close();
    }
})();
