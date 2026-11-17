"""Offline Chromium proof: synthetic same-origin card and ZIP, no external requests."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from scripts.research.commercial_document_acquisition import download_b2b, observe

CARD='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
FILE='https://www.b2b-center.ru/fixture-docs.zip'
HTML='''<html><body><h1>Закупка №4664540</h1><button onclick="document.querySelector('#files').hidden=false">Позиции</button><button id="files" hidden onclick="document.querySelector('#doc').hidden=false">Скачать файлом</button><a id="doc" hidden href="/fixture-docs.zip">Закупочная документация</a></body></html>'''


def main():
    from playwright.sync_api import sync_playwright

    buf=BytesIO()
    with ZipFile(buf,'w') as z:z.writestr('spec.txt','Test requirements')
    with sync_playwright() as driver, TemporaryDirectory() as tmp:
        browser=driver.chromium.launch(channel='chrome',headless=True,timeout=8000)
        context=browser.new_context(accept_downloads=True,service_workers='block')
        seen=[]
        def route(r):
            seen.append(r.request.url)
            if r.request.url==CARD:r.fulfill(status=200,content_type='text/html; charset=utf-8',body=HTML)
            elif r.request.url==FILE:r.fulfill(status=200,headers={'Content-Type':'application/zip','Content-Length':str(len(buf.getvalue())),'Content-Disposition':'attachment; filename="docs.zip"'},body=buf.getvalue())
            else:r.abort()
        context.route('**/*',route);page=context.new_page()
        try:
            page.goto(CARD,wait_until='domcontentloaded',timeout=8000)
            assert observe(page,CARD,authenticated=False)['state']=='B2B_AUTHORIZED_UI_OR_API_REQUIRED'
            dest=Path(tmp)/'fixture.zip'
            receipt=download_b2b(page,CARD,dest,authorized=True)
            assert receipt['members']==[{'name':'spec.txt','size_bytes':17}]
            assert dest.read_bytes()==buf.getvalue() and seen==[CARD,FILE]
            print('CHROMIUM OFFLINE DOWNLOAD PASS',receipt['sha256'],'bytes',receipt['size_bytes'])
        finally:context.close();browser.close()


if __name__=='__main__':main()
