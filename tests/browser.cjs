/* Browser regression checks against a running synthetic demo. Run on a disposable database. */
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
let server;

(async () => {
  if (!process.env.AQUAWATCH_URL) {
    fs.mkdirSync('runtime', {recursive:true});
    const directory=fs.mkdtempSync(path.resolve('runtime/e2e-'));
    server=spawn(process.env.AQUAWATCH_PYTHON || 'python', ['-m','uvicorn','aquawatch.api:app','--host','127.0.0.1','--port','8011'], {
      env:{...process.env,DATABASE_URL:`sqlite:///${path.join(directory,'demo.sqlite').replaceAll('\\','/')}`},windowsHide:true,stdio:'ignore'
    });
    for(let attempt=0;attempt<80;attempt++) {
      try {if((await fetch('http://127.0.0.1:8011/health')).ok)break;} catch {}
      if(attempt===79) throw new Error('Test server did not become ready');
      await new Promise(resolve=>setTimeout(resolve,100));
    }
  }
  const browser = await chromium.launch({headless: true, ...(process.env.AQUAWATCH_BROWSER_CHANNEL ? {channel:process.env.AQUAWATCH_BROWSER_CHANNEL} : {})});
  const context = await browser.newContext({viewport: {width: 1440, height: 1080}, reducedMotion: 'reduce'});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const base = process.env.AQUAWATCH_URL || 'http://127.0.0.1:8011';
  const images = path.resolve('docs/images'); fs.mkdirSync(images, {recursive: true});
  await page.goto(base);
  await page.getByText('Network connected', {exact: true}).waitFor();
  await page.getByRole('heading', {name:'Every reading tells a story.'}).waitFor();
  assert.equal(await page.locator('#metrics .metric').count(), 4);
  await page.screenshot({path:path.join(images, 'dashboard.png'), fullPage:true});
  await page.getByRole('button', {name:'7 days'}).click();
  assert.equal(await page.getByRole('button', {name:'7 days'}).getAttribute('aria-pressed'), 'true');
  await page.locator('#network-chart').focus();
  const lastReading=await page.locator('#chart-reading').textContent();
  await page.keyboard.press('ArrowLeft');
  assert.notEqual(await page.locator('#chart-reading').textContent(),lastReading);
  await page.locator('[data-kind="billing_mismatch"]').click();
  assert.equal(await page.locator('#kind-filter').inputValue(),'billing_mismatch');
  await page.getByRole('button',{name:'Clear filters'}).click();
  assert.equal(await page.locator('#kind-filter').inputValue(),'all');
  await page.getByRole('link', {name:/Investigations/}).click();
  await page.getByRole('searchbox').fill('M-0001');
  await page.waitForFunction(() => document.querySelector('#queue-label')?.textContent === '1 investigation');
  await page.getByRole('button', {name:'Sustained unusual consumption',exact:true}).click();
  await page.getByRole('dialog', {name:'Sustained unusual consumption'}).waitFor();
  await page.screenshot({path:path.join(images, 'investigation.png'), fullPage:true});
  await page.getByLabel('Investigation note').fill('Browser test: verify readings before requesting site inspection.');
  await page.getByRole('button', {name:'Save decision'}).click();
  await page.getByText('Decision saved. Your note is recorded in the case history.').waitFor();
  await page.reload();
  await page.getByText('Network connected', {exact:true}).waitFor();
  await page.getByRole('searchbox').fill('M-0001');
  await page.waitForFunction(() => document.querySelector('#queue-label')?.textContent === '1 investigation');
  await page.getByRole('button', {name:'Sustained unusual consumption',exact:true}).click();
  await page.getByText('Browser test: verify readings before requesting site inspection.',{exact:true}).first().waitFor();
  await page.getByLabel('Next status').selectOption('open');
  await page.getByLabel('Investigation note').fill('Browser test complete: reopened for the portfolio demonstration.');
  await page.getByRole('button', {name:'Save decision'}).click();
  await page.getByText('Decision saved. Your note is recorded in the case history.').waitFor();
  await page.getByRole('button', {name:'Close investigation',exact:true}).click();
  await page.getByRole('link', {name:'Data pipeline',exact:false}).click();
  await page.locator('#view-pipeline .import-demo').click();
  await page.waitForFunction(() => document.querySelector('#toast')?.textContent.includes('imported'));
  await page.locator('#view-pipeline .import-demo').click();
  await page.getByText('Already imported. Replay verified: no new readings or duplicate cases.').waitFor();
  await page.getByRole('button',{name:'synthetic-baseline.csv',exact:true}).click();
  await page.getByText('8 quarantined rows. Original accepted records are preserved.').waitFor();
  await page.getByRole('button',{name:'Close import details'}).click();
  await page.getByRole('link',{name:'Model & evidence'}).click();
  await page.getByText('86.2%',{exact:true}).waitFor();
  await page.locator('#toast').waitFor({state:'hidden'});
  await page.screenshot({path:path.join(images,'methodology.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('link',{name:'Overview',exact:false}).first().click();
  await page.getByRole('heading',{name:'Every reading tells a story.'}).waitFor();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Page overflows mobile viewport');
  await page.screenshot({path:path.join(images,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[], 'Browser raised JavaScript errors');
  console.log('Browser checks passed: overview, filters, investigation persistence, state transition, import replay, quarantine, benchmark, mobile layout; no JavaScript errors.');
  await browser.close();
})().catch(error => { console.error(error); process.exitCode=1; }).finally(()=>{if(server)server.kill();});
