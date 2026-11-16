from zipfile import ZipFile

import pytest

from scripts.research.commercial_document_acquisition import (
    archive_receipt,
    plan,
    route_permitted,
)

B2B='https://www.b2b-center.ru/app/market-next/fixture/tender-4664540/'
WORKSPACE='https://workspace.ru/tenders/fixture-19019/'


def test_public_access_rules_and_exact_identity():
    assert plan(B2B,'Закупка №4664540',['Позиции'])['state']=='B2B_AUTHORIZED_UI_OR_API_REQUIRED'
    assert plan(B2B,'Закупка №4664540',['Позиции'],authenticated=True)['state']=='B2B_DOCUMENTED_UI_READY'
    assert plan(B2B,'Закупка №4664541',['Позиции'],authenticated=True)['state']=='B2B_AUTHORIZED_UI_OR_API_REQUIRED'
    assert plan(WORKSPACE,'Файлы для скачивания доступны участникам с PRO-аккаунтом',[])['state']=='WORKSPACE_ENTITLEMENT_REQUIRED'
    assert plan(B2B,'Подтвердите, что вы не робот',[],authenticated=True)['state']=='ACCESS_CHALLENGE'
    assert route_permitted(B2B,B2B,'GET','document')
    assert not route_permitted(B2B,'https://evil.invalid/a','GET','document')
    assert not route_permitted(B2B,B2B,'POST','xhr')
    assert not route_permitted(B2B,'http://www.b2b-center.ru/a','GET','document')


def test_zip_manifest_and_unsafe_archive(tmp_path):
    p=tmp_path/'docs.zip'
    with ZipFile(p,'w') as z:z.writestr('spec.txt','fixture')
    receipt=archive_receipt(p)
    assert receipt['members']==[{'name':'spec.txt','size_bytes':7}]
    assert not receipt['complete_documentation_verified']
    with ZipFile(p,'w') as z:z.writestr('../escape.txt','x')
    with pytest.raises(ValueError):archive_receipt(p)
