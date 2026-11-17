'use strict';
const assert=require('node:assert/strict');
const {chromium}=require(process.env.APR08_PLAYWRIGHT_MODULE);
const origin=process.env.APR08_BROWSER_ORIGIN;
const run=process.env.APR08_BROWSER_RUN;
const target=new URL(origin);
assert.equal(target.hostname,'127.0.0.1');assert.equal(target.protocol,'http:');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.APR08_CHROME,headless:true,args:['--disable-background-networking','--no-first-run']});
 try{
  const context=await browser.newContext({viewport:process.env.APR08_BROWSER_NARROW==='1'?{width:390,height:844}:{width:1280,height:900},serviceWorkers:'block',httpCredentials:{username:'apr08-replay',password:process.env.APR08_BROWSER_PASSWORD}});
  await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  const page=await context.newPage();page.setDefaultTimeout(8000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const l=id=>page.locator('#'+id);
  await page.goto(origin+'/pilot/tender-agent/workspace?run='+run);
  await l('copilot-panel').waitFor({state:'visible'});
  if(['pinned','ri223','ri223-multilot','ri223-attachments','ri223-container'].includes(process.env.APR08_BROWSER_SCENARIO)) assert(await l('report-panel').isHidden());
  else await l('report-panel').waitFor({state:'visible'});
  await page.getByText('Evidence Copilot — вопросы и расчёт по закупке',{exact:true}).click();
  const ask=async(question,pattern)=>{
    await l('copilot-answer-question').fill(question);
    const response=page.waitForResponse(r=>r.url().endsWith('/evidence-answer')&&r.request().method()==='POST');
    await l('copilot-answer-submit').click();assert.equal((await response).status(),200);
    await page.waitForFunction(({id,text})=>document.getElementById(id).innerText.includes(text),{id:'copilot-answer-result',text:pattern});
    return await l('copilot-answer-result').innerText();
  };
  if(process.env.APR08_BROWSER_SCENARIO==='ri223-container') {
    await ask('Покажи архивные сведения 223-ФЗ','Цена единственного лота: 1020000');
    await l('copilot-search').fill('критерий оценки');await l('copilot-search-submit').click();
    await page.waitForFunction(()=>document.getElementById('copilot-search-result').innerText.includes('SHA-256 контейнера'));
    await l('copilot-search-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/ri223-container.png'});
    assert(await l('analyze-btn').isDisabled());assert.deepEqual(errors,[]);
    console.log('APR03B_RI223_CONTAINER_BROWSER_PASS');return;
  }
  if(process.env.APR08_BROWSER_SCENARIO==='ri223-attachments') {
    await ask('Покажи архивные сведения 223-ФЗ','Цена единственного лота: 191352');
    await l('copilot-search').fill('договор');await l('copilot-search-submit').click();
    await page.waitForFunction(()=>document.getElementById('copilot-search-result').innerText.includes('SHA-256'));
    await l('copilot-search-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/ri223-attachments.png'});
    assert(await l('analyze-btn').isDisabled());assert.deepEqual(errors,[]);
    console.log('APR03B_RI223_ATTACHMENT_BROWSER_PASS');return;
  }
  if(process.env.APR08_BROWSER_SCENARIO==='ri223-multilot') {
    const observed=await ask('Покажи архивные сведения 223-ФЗ','Цена единственного лота: UNKNOWN');
    assert.match(observed,/Конкурс в электронной форме/);assert.match(observed,/Редакция 3/);
    assert.match(observed,/правовой статус закупки, обеспечение и победитель: UNKNOWN/);
    await ask('Какова НМЦК?','UNKNOWN');assert(await l('analyze-btn').isDisabled());
    assert.deepEqual(errors,[]);assert(await l('report-panel').isHidden());
    console.log('APR03B_RI223_MULTILOT_BROWSER_PASS no aggregate price or analysis');return;
  }
  if(process.env.APR08_BROWSER_SCENARIO==='ri223') {
    const observed=await ask('Покажи архивные сведения 223-ФЗ','Цена единственного лота: 191352');
    assert.match(observed,/Запрос котировок/);assert.match(observed,/2026-10-15T10:00:00/);
    assert.match(observed,/часовой пояс UNKNOWN/);assert.match(observed,/Валюта лота: RUB/);
    assert.match(observed,/правовой статус закупки, обеспечение и победитель: UNKNOWN/);
    assert.equal(await l('copilot-answer-result').getByText('Проверенный оригинал XML ЕИС:',{exact:false}).count(),5);
    await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/ri223.png'});
    await ask('Какова НМЦК?','UNKNOWN');await ask('Какой размер обеспечения заявки?','UNKNOWN');
    assert.deepEqual(errors,[]);assert(await l('report-panel').isHidden());
    console.log('APR03B_RI223_BROWSER_PASS five cited fields, no 44-FZ fallback');return;
  }
  if(process.env.APR08_BROWSER_SCENARIO==='pinned') {
    const fixed=async(question,pattern,percent)=>{
      await l('copilot-question').selectOption(question);
      if(percent!==undefined) await l('copilot-percent').fill(percent);
      await l('copilot-submit').click();
      await page.waitForFunction(text=>document.getElementById('copilot-result').innerText.includes(text),pattern);
      return await l('copilot-result').innerText();
    };
    assert.match(await fixed('subject','Проверенный оригинал XML ЕИС'),/XML:/);
    assert.match(await fixed('nmck','1245000'),/Проверенный оригинал XML ЕИС/);
    assert.match(await fixed('deadline','2026-10-19'),/Проверенный оригинал XML ЕИС/);
    assert.match(await fixed('nmck_percent','62250.00','5'),/Не установленное обеспечение/);
    assert.match(await ask('Какова НМЦК?','1245000'),/Проверенный оригинал XML ЕИС/);
    assert.match(await ask('Какой размер обеспечения заявки?','6225.00'),/0.5%|0,5%/);
    await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/bid-security.png'});
    assert.match(await ask('Какой размер обеспечения исполнения контракта?','30.0%'),/Сумма в XML: UNKNOWN/);
    await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/contract-security.png'});
    assert.match(await ask('Поясни требования к обеспечению заявки','Ссылки заказчика на нормы'),/ст\. 45|стать[яие] 45/i);
    const legal=await ask('Поясни требования к обеспечению исполнения контракта','Ссылки заказчика на нормы');
    assert.match(legal,/содержание законодательства не проверено/);assert.match(legal,/44-ФЗ/);
    await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/legal.png'});
    if(process.env.APR08_STATUTE_BROWSER_ACCEPTANCE==='1') {
      const historical=await ask('Покажи статью 45 44-ФЗ из снимка 14.07.2022','Неполный исторический фрагмент');
      assert.match(historical,/Статья 45\. Условия независимой гарантии/);
      assert.match(historical,/rospatent\.gov\.ru/);assert.match(historical,/SHA-256 8cc95985d65d6913861ca42d4b67fd2ce42adca25a132ce17c82e03d052d433d/);
      await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/historical-statute.png'});
      const asOf=await ask('Покажи статью 45 44-ФЗ на дату 14.07.2022','UNKNOWN');
      assert(!asOf.includes('Статья 45. Условия'));
      await ask('Покажи статью 45 44-ФЗ на дату 17.11.2026','UNKNOWN');
      console.log('APR08_STATUTE_BROWSER_PASS historical source SHA and two as-of refusals');
      if(process.env.APR08_GOVERNMENT_COPIES_BROWSER==='1') {
        const docx=await ask('Покажи статью 45 44-ФЗ из копии от 03.11.2026','Неполный исторический фрагмент');
        assert.match(docx,/Статья 45[.] Условия независимой гарантии/);assert.match(docx,/word\/document.xml/);
        const pdf=await ask('Покажи статью 3.2 223-ФЗ из копии от 07.06.2025','Неполный исторический фрагмент');
        assert.match(pdf,/Статья 3[.]2[.] Порядок осуществления конкурентной закупки/);assert.match(pdf,/pinned projection/);
        const compare44=await ask('Сравни списки изменений 44-ФЗ','Сопоставление перечней');
        assert.match(compare44,/278-ФЗ · в раннем фрагменте: не указан; в позднем: указан/);
        const compare223=await ask('Сравни списки изменений 223-ФЗ','Сопоставление перечней');
        assert.match(compare223,/318-ФЗ · в раннем фрагменте: не указан; в позднем: указан/);
        await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/government-copy-comparison.png'});
        await ask('Покажи статью 45 44-ФЗ на дату 03.11.2026','UNKNOWN');
        console.log('APR08_GOVERNMENT_COPIES_BROWSER_PASS docx pdf comparison current-law refusal');
      }

      if(process.env.APR08_AMENDMENT_BROWSER_ACCEPTANCE==='1') {
        const timing=await ask('Покажи сроки вступления в силу 279-ФЗ на дату 17.11.2026','Юридический статус нормы на выбранную дату: UNKNOWN');
        assert.match(timing,/2027-01-01 · Будущая дата/);assert.match(timing,/2026-10-01 · Дата наступила/);assert.match(timing,/2026-08-04 · Дата наступила/);
        assert.match(timing,/Дата публикации|дата публикации по справочному источнику/);
        await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/amendment-timing.png'});
        await ask('Покажи статью 45 44-ФЗ на дату 17.11.2026','UNKNOWN');
        console.log('APR08_AMENDMENT_BROWSER_PASS secondary schedule, future group, current-law refusal');
      }

    }
    if(process.env.APR08_COMPOSED_BROWSER==='1') {
      const brief=await ask('Составь сводку условий закупки работ с расчётом 5% НМЦК','Разделы с источниками: 7 из 9');
      assert.match(brief,/1245000/);assert.match(brief,/62250[.]00/);assert.match(brief,/30[.]0%/);
      assert.match(brief,/фактическая прибыль и потребность в средствах: UNKNOWN/);
      assert.equal(await l('copilot-answer-result').locator('details').count(),9);
      await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/composed-xml.png'});
      const comparison=await ask('Сопоставь обеспечение исполнения контракта и статью 96 44-ФЗ из копии от 03.11.2026','Разделы с источниками: 3 из 3');
      assert.match(comparison,/Сумма в XML: UNKNOWN/);assert.match(comparison,/Статья 96[.] Обеспечение исполнения контракта/);assert.match(comparison,/содержание законодательства не проверено/);
      await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/composed-legal.png'});
      console.log('APR08_COMPOSED_PINNED_BROWSER_PASS brief 7/9 legal comparison 3/3');
    }
    await ask('Можно ли подписывать контракт?','UNKNOWN');
    await l('copilot-answer-question').fill('другой вопрос');assert.equal(await l('copilot-answer-result').innerText(),'');
    assert(await l('report-panel').isHidden()); assert.deepEqual(errors,[]);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Unexpected horizontal page overflow');
    console.log('APR08_PINNED_XML_CHROMIUM_PASS subject NMCK deadline percent security legal unknown clear no report no errors');return;
  }
  assert.match(await ask('Какой срок оплаты услуг?','7 рабочих дней'),/SHA-256 оригинала/);
  await page.locator('#copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/payment.png'});
  assert.match(await ask('Какой срок оказания услуг?','07.12.2026'),/включительно/);
  assert.equal(await l('copilot-answer-result').getByText('Указано в источнике:',{exact:false}).count(),1);
  assert.equal(await l('copilot-answer-result').getByText('SHA-256 оригинала',{exact:false}).count(),2);
  await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/delivery.png'});
  await ask('Можно ли подписывать контракт?','UNKNOWN');
  await ask('Какова НМЦК?','UNKNOWN'); // this legacy archived run has no pinned notice receipt
  if(process.env.APR08_COMPOSED_BROWSER==='1') {
    const brief=await ask('Составь сводку условий закупки услуг','Разделы с источниками: 2 из 8');
    assert.match(brief,/7 рабочих дней/);assert.match(brief,/07[.]12[.]2026/);assert.match(brief,/SHA-256 оригинала/);assert.match(brief,/UNKNOWN/);
    assert.equal(await l('copilot-answer-result').locator('details').count(),8);
    await l('copilot-answer-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/composed-documents.png'});
    console.log('APR08_COMPOSED_DP_BROWSER_PASS brief 2/8 independent original citations');
  }

  await l('copilot-search').fill('оплата работ');await l('copilot-search-submit').click();
  await page.waitForFunction(()=>document.getElementById('copilot-search-result').innerText.includes('SHA-256'));
  await l('copilot-search').fill('иная тема');assert.equal(await l('copilot-search-result').innerText(),'');
  for(const [id,value] of Object.entries({'cost-external':'100','cost-labor':'200','cost-reserve':'20','cost-fixed':'5','cost-tax':'6','cost-variable':'2','cost-target':'50'}))await l(id).fill(value);
  await l('cost-offer-enabled').check();
  for(const [id,value] of Object.entries({'cost-offer-price':'500','cost-guarantee-fees':'10','cost-bid-cash':'30','cost-contract-cash':'40'}))await l(id).fill(value);
  await l('cost-scenario-confirm').check();await page.locator('#price-cost-form button[type=submit]').click();
  await page.waitForFunction(()=>document.getElementById('price-cost-result').innerText.includes('245,00'));
  const money=await l('price-cost-result').innerText();assert.match(money,/125,00/);assert.match(money,/UNKNOWN/);
  await l('price-cost-result').screenshot({path:process.env.APR08_SCREENSHOT_DIR+'/finance.png'});
  await l('cost-offer-price').fill('501');assert.equal(await l('price-cost-result').innerText(),'');
  await l('cost-clear-btn').click();assert(!await l('cost-offer-enabled').isChecked());
  assert.deepEqual(errors,[]);console.log('APR08_REAL_CHROMIUM_PASS payment delivery unknown legacy search finance clear; no page errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exitCode=1});
