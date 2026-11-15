from scripts.research.report_sibur_remaining_work import build,site

def test_site_affiliation_and_conflicts():
    org='ПАО "Нижнекамскнефтехим"'
    assert site({'organizer':org,'site_mentions':[]})==('Нижнекамскнефтехим','organizer_affiliation_only')
    assert site({'organizer':org,'site_mentions':['ЗапСибНефтехим']})[0]=='UNRESOLVED_CONFLICT'
    assert site({'organizer':org,'site_mentions':['ЗапСибНефтехим','Нижнекамскнефтехим']})[0]=='MULTI_SITE'

def test_pending_url_dedup_and_exact_pairs():
    u='https://www.sibur.ru/test.xlsx'; v='https://www.sibur.ru/test.pdf'
    snap=[{'external_id':i,'observations':[{'documentation_urls':urls}]} for i,urls in [('A',[u,v]),('B',[u])]]
    proj=[{'project_id':'P','priority_recommendation':'P0','archive_publication_ids':['A']}]
    routing=[{'external_id':'B','channels':['industrial_equipment']}]
    sales=[{'external_id':'B','organizer':'central','site_mentions':[],'service_signal':False,'budget_signal':False,'core_tags':['KIP'],'source_receipts':[]}]
    db=[{'external_id':'A','sha256':'h','raw_meta':{'capture_receipts':[{'url':u,'reference':{'external_id':'A'}}]}}]
    result=build(snap,proj,routing,sales,db,{'h':'extracted'});s=result['summary'];assert s['priority_unique_publications']==2 and s['pending_pair_urls']==2 and s['pending_without_extracted_pair']==1 and s['p0_pending_urls']==1;assert result['pending_urls'][0]['url']==v and result['pending_urls'][1]['needs_acquisition'] is False;assert result['site_groups']['UNRESOLVED']['total']==1
