from scripts.research.report_sibur_coverage import calculate

def test_coverage_counts_shared_documents_distinct_projects_and_unknown_formats():
    a='https://www.sibur.ru/upload/tmp/example/a/a.xlsx';b='https://www.sibur.ru/upload/tmp/example/b/b.7z';c='https://www.sibur.ru/upload/tmp/example/c/c.docx'
    snap=[{'external_id':i,'observations':[{'documentation_urls':urls,'unverified_document_links':u}]} for i,urls,u in [('1',[a,b],0),('2',[a,c],1),('3',[],0)]]
    projects=[{'project_id':i,'name':i,'priority_recommendation':'P0','archive_publication_ids':ids} for i,ids in [('A',['1','2']),('B',['2','3'])]]
    route=[{'external_id':'1','channels':['industrial_equipment']},{'external_id':'2','channels':['industrial_equipment']}]
    db=[{'external_id':i,'sha256':sha,'raw_meta':{'capture_receipts':[{'url':url,'reference':{'external_id':i}}]}} for i,sha,url in [('1','a',a),('2','a',a),('2','c',c)]]
    data=calculate(snap,projects,route,db,{'a':'extracted','c':'review'});all_=data['cohorts'][0];assert all_['total']==3 and all_['extracted_any']==2 and all_['all_supported_extracted']==1 and all_['all_known_no_unverified']==0;assert all_['supported_urls']==2 and all_['extracted_supported_urls']==1 and all_['hashes']==2;assert data['memberships']==4 and next(x for x in data['cohorts'] if x['name']=='priority_union')['total']==3
