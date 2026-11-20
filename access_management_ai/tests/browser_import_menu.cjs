/* Import visibility regression; fixture mutations require an isolated DB. */
const puppeteer = require(process.env.AM20_PUPPETEER || '/home/synconics/.npm/_npx/55158e48eb5c59f7/node_modules/puppeteer');
const assert = require('node:assert/strict');
const base = process.env.AM20_URL || 'http://127.0.0.1:2223';
const db = process.env.AM20_DB || 'am20_audit_20260918';
const artifacts = process.env.AM20_ARTIFACTS || '/tmp/am20-contact-import';
assert.notEqual(db, 'v20_ent', 'Run fixtures only in an isolated database');
(async () => {
 const browser = await puppeteer.launch({executablePath:'/usr/bin/google-chrome',headless:true,
  args:['--no-sandbox','--disable-dev-shm-usage'],defaultViewport:{width:1440,height:1000}});
 const admin = await browser.newPage();
 const context = await browser.createBrowserContext();
 const page = await context.newPage();
 const errors=[];
 page.on('pageerror',error=>errors.push(String(error)));
 const rpc = (p,path,params)=>p.evaluate(async({path,params})=>fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({jsonrpc:'2.0',method:'call',params,id:1})}).then(r=>r.json()),{path,params});
 const call=async(p,model,method,args,kwargs={})=>{
  const data=await rpc(p,`/web/dataset/call_kw/${model}/${method}`,{model,method,args,kwargs});
  if(data.error)throw Error(JSON.stringify(data.error));return data.result;
 };
 const login=async(p,login,password)=>{
  await p.goto(`${base}/web/login?db=${db}`,{waitUntil:'domcontentloaded'});
  const result=await rpc(p,'/web/session/authenticate',{db,login,password});assert.ok(result.result?.uid);
 };
 const open=async(type='list')=>{
  await page.goto(`${base}/odoo?debug=assets`,{waitUntil:'networkidle2'});
  await page.waitForFunction(()=>Boolean(window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.action));
  await page.evaluate(async type=>odoo.__WOWL_DEBUG__.root.env.services.action.doAction({type:'ir.actions.act_window',
   name:'Contacts',res_model:'res.partner',views:[[false,type]],target:'current'}),type);
  await page.waitForSelector(type==='list'?'.o_data_row':'.o_kanban_record');
 };
 const checkMenu=async(allowed)=>{
  const button=await page.$('button[aria-label="Actions menu"]');
  if(allowed)assert.ok(button,'Actions menu must be rendered');
  if(button){await button.click();await page.waitForSelector('.o-dropdown--menu');}
  if(allowed)await page.waitForSelector('.o_import_menu',{visible:true});
  else assert.equal(await page.$('.o_import_menu'),null,'Import restriction remains effective');
  if(button)await page.keyboard.press('Escape');
 };
 try{
  await login(admin,'admin',process.env.AM20_PASSWORD||'a');
  const ref=async name=>(await call(admin,'ir.model.data','search_read',[[['module','=','base'],['name','=',name]]],{fields:['res_id']}))[0].res_id;
  const create=async(model,values)=>(await call(admin,model,'create',[[values]],{context:{no_reset_password:true,tracking_disable:true}}))[0];
  const loginName=`am20_import_${Date.now()}`;
  const user=await create('res.users',{name:'AM20 import menu user',login:loginName,password:'am20-browser',
   group_ids:[[6,0,await Promise.all(['group_user','group_partner_manager','group_allow_export'].map(ref))]]});
  const profile=await create('access.management',{name:'AM20 import menu profile',user_ids:[[4,user]]});
  const [model]=await call(admin,'ir.model','search_read',[[['model','=','res.partner']]],{fields:['id']});
  const line=await create('access.management.model',{rule_id:profile,model_id:model.id});
  await login(page,loginName,'am20-browser');
  for(const type of ['list','kanban']){await open(type);await checkMenu(true);}
  await open();
  await page.click('button[aria-label="Actions menu"]');await page.waitForSelector('.o_import_menu',{visible:true});
  await page.click('.o_import_menu');await page.waitForSelector('.o_import_file',{visible:true});
  await page.screenshot({path:`${artifacts}/import-upload.png`});
  console.log('IMPORT_LIST_KANBAN_AND_UPLOAD_OK');
  for(const field of ['global_hide_import','readonly']){
   await call(admin,'access.management','write',[[profile],{[field]:true}]);await open();await checkMenu(false);
   await call(admin,'access.management','write',[[profile],{[field]:false}]);
  }
  await call(admin,'access.management.model','write',[[line],{hide_import_button:true}]);await open();await checkMenu(false);
  await call(admin,'access.management.model','write',[[line],{hide_import_button:false,perm_create:false}]);await open();await checkMenu(false);
  await call(admin,'access.management.model','write',[[line],{perm_create:true}]);await open();await checkMenu(true);
  console.log('IMPORT_RESTRICTIONS_AND_RESTORATION_OK');
  assert.deepEqual(errors,[]);console.log('ERRORS',JSON.stringify(errors));
 }catch(error){console.error(error.stack);await page.screenshot({path:`${artifacts}/import-failure.png`}).catch(()=>{});process.exitCode=1;}
 finally{await browser.close();}
})();
