/* Module management controls and RPC denial. Fixtures run only in a test DB. */
const puppeteer = require(process.env.AM20_PUPPETEER || '/home/synconics/.npm/_npx/55158e48eb5c59f7/node_modules/puppeteer');
const assert = require('node:assert/strict');
const base = process.env.AM20_URL || 'http://127.0.0.1:2223';
const db = process.env.AM20_DB || 'am20_audit_20260918';
const artifacts = process.env.AM20_ARTIFACTS || '/tmp/am20-module-block';
assert.notEqual(db, 'v20_ent', 'Use an isolated database');
const methods = ['button_install', 'button_upgrade', 'button_uninstall', 'button_immediate_install',
    'button_immediate_upgrade', 'button_immediate_uninstall', 'button_uninstall_wizard',
    'button_immediate_install_app', 'module_uninstall', 'update_list'];
const selector = methods.map(name => `[name="${name}"]`).join(',');

(async () => {
    const browser = await puppeteer.launch({executablePath: '/usr/bin/google-chrome', headless: true,
        args: ['--no-sandbox', '--disable-dev-shm-usage'], defaultViewport: {width: 1440, height: 1000}});
    const admin = await browser.newPage();
    const context = await browser.createBrowserContext();
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    const rpc = (p, path, params) => p.evaluate(async ({path, params}) =>
        fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({jsonrpc: '2.0', method: 'call', params, id: 1})}).then(r => r.json()), {path, params});
    const call = async (p, model, method, args, kwargs = {}) => {
        const result = await rpc(p, `/web/dataset/call_kw/${model}/${method}`, {model, method, args, kwargs});
        if (result.error) throw new Error(JSON.stringify(result.error));
        return result.result;
    };
    const login = async (p, login, password) => {
        await p.goto(`${base}/web/login?db=${db}`, {waitUntil: 'domcontentloaded'});
        const result = await rpc(p, '/web/session/authenticate', {db, login, password});
        assert.ok(result.result?.is_system, 'Test account has native module management privileges');
    };
    const load = async () => {
        await page.goto(`${base}/odoo?debug=assets`, {waitUntil: 'networkidle2'});
        await page.waitForFunction(() => Boolean(window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.action));
    };
    const open = async (type, id) => {
        await page.evaluate(async ({type, id}) => odoo.__WOWL_DEBUG__.root.env.services.action.doAction({
            type: 'ir.actions.act_window', name: 'Apps', res_model: 'ir.module.module',
            domain: [['name', '=', 'access_management_ai']], res_id: id || false,
            views: [[false, type]], target: 'current'}), {type, id});
        await page.waitForSelector(`.o_${type}_view`);
        await page.waitForFunction(() => document.querySelector('.o_form_view,.o_kanban_record,.o_data_row'));
    };
    try {
        await login(admin, 'admin', process.env.AM20_PASSWORD || 'a');
        const group = (await call(admin, 'ir.model.data', 'search_read', [[['module', '=', 'base'], ['name', '=', 'group_system']]], {fields: ['res_id']}))[0].res_id;
        const loginName = `am20_module_${Date.now()}`;
        const [userId] = await call(admin, 'res.users', 'create', [[{name: 'AM20 module browser user', login: loginName,
            password: 'am20-browser', group_ids: [[6, 0, [group]]]}]], {context: {no_reset_password: true}});
        const [profileId] = await call(admin, 'access.management', 'create', [[{name: 'AM20 module browser rule', user_ids: [[4, userId]]}]]);
        const [module] = await call(admin, 'ir.module.module', 'search_read', [[['name', '=', 'access_management_ai']]], {fields: ['state']});
        await login(page, loginName, 'am20-browser');
        await load();
        await open('form', module.id);
        await page.waitForSelector('[name="button_immediate_upgrade"]', {visible: true});
        await call(admin, 'access.management', 'write', [[profileId], {block_module_management: true}]);
        await load();
        for (const type of ['form', 'kanban', 'list']) {
            await open(type, type === 'form' ? module.id : false);
            assert.equal(await page.$(selector), null, `${type}: module-changing controls are absent`);
        }
        for (const method of methods) {
            const result = await rpc(page, `/web/dataset/call_kw/ir.module.module/${method}`,
                {model: 'ir.module.module', method, args: [[module.id]], kwargs: {}});
            assert.equal(result.error?.data?.name, 'odoo.exceptions.AccessError', method);
        }
        assert.equal((await call(admin, 'ir.module.module', 'read', [[module.id], ['state']]))[0].state, module.state);
        await page.screenshot({path: `${artifacts}/module-blocked.png`});
        console.log('MODULE_VIEWS_AND_ALL_RPC_GUARDS_OK');
        await call(admin, 'access.management', 'write', [[profileId], {block_module_management: false}]);
        await load();
        await open('form', module.id);
        await page.waitForSelector('[name="button_immediate_upgrade"]', {visible: true});
        await page.waitForSelector('[name="button_uninstall_wizard"]', {visible: true});
        assert.deepEqual(errors, []);
        console.log('MODULE_CONTROLS_RESTORED_OK', 'ERRORS', JSON.stringify(errors));
    } catch (error) {
        console.error(error.stack);
        await page.screenshot({path: `${artifacts}/module-block-failure.png`}).catch(() => {});
        process.exitCode = 1;
    } finally { await browser.close(); }
})();
