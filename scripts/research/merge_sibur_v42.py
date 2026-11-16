"""Merge checkpointed V42 observations; preserve prior originals and scope, no DB access."""
import argparse, collections, copy, hashlib, json, os
from decimal import Decimal
from pathlib import Path

EXPECTED={
 'consolidated-project-map-v41.json':'0daefd4f8a12dd7327708d2ff32aa7ac0705b1a6f4a1a26cc5139d05145a4826',
 'consolidated-project-report-v41.md':'70e37971f5a08faaeee826520b9821f73e2036735f2ee8d9ddd79122bdc39928',
 'commercial-action-register-v35.json':'932ae210ad826d57fa9428b0cf73582a917846e6b1230cae36d941cfd2762bff',
 'commercial-outcome-queue-v16.json':'afd129e3c2301b32fba0f234b7d63831f851cb9aaf9579e298e760c9335dabbb',
 'sionika-contract-corpus-audit-v1.json':'2327f270b4240fec91f13cd858f532d44f8b3743b6f1f972725775468edebc1b',
 'project-coverage-dashboard-v28-post-storage-recovery.json':'481d650720cd39b68cd2b9725e2c5d8d9ad121291b0218720072800f78ebaf87',
}
DEADLINES=[
 ('2145723/1','TNH_ASUTP_1178','2026-11-17 11:00','https://zakupki.kontur.ru/IS87286268'),
 ('2146167/1','STG_AUMA_SERVICE','2026-11-18 14:00','https://zakupki.kontur.ru/IS88558503'),
 ('2146194/1','AGHK','2026-11-18 15:00','https://zakupki.kontur.ru/IS88650131'),
 ('2145706/1','NKNH_MOTOR_SERVICE','2026-11-23 11:00','https://energybase.ru/tender/01a1afc8-37e7-73e3-95aa-284a8792580d'),
 ('2146492/1','STYRENE','2026-11-27 11:00','https://www.sibur.ru/ru/procurement/buy/'),
]
NEW_PRICES=[('51651052730260000540000','2026-08-18','ТО ионных хроматографов 761 COMPACT IC','218502.00','core'),('51651052730260000580000','2026-09-03','650 м кабеля АВВГнг(А)-LS 4x25','160439.76','core'),('51651052730260000470000','2026-07-06','КМО301НЖ50НЗУ, 1 шт.','345845.60','adjacent')]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2)
 return sha(p)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);args=ap.parse_args();p=args.root;os.umask(0o077)
 for name,h in EXPECTED.items():assert sha(p/name)==h,name
 m=load(p/'consolidated-project-map-v41.json');a=load(p/'commercial-action-register-v35.json');q=load(p/'commercial-outcome-queue-v16.json');c=load(p/'sionika-contract-corpus-audit-v1.json');cov=load(p/'project-coverage-dashboard-v28-post-storage-recovery.json')
 old=copy.deepcopy(m);oldq=copy.deepcopy(q);olda=copy.deepcopy(a)
 projects={x['project_id']:x for x in m['projects']};actions={x['project_id']:x for x in a['rows']};queue={x['external_id']:x for x in q['rows']}
 assert len(projects)==len(actions)==66 and len(queue)==8244 and len({i for x in projects.values() for i in x['archive_publication_ids']})==2659
 previews=[]
 for ident,project,deadline,source in DEADLINES:
  assert ident in projects[project]['archive_publication_ids'] and project in queue[ident]['project_ids']
  observation={'id':ident,'project_id':project,'reported_deadline_msk':deadline,'source':source,'observed_date':'2026-11-16','eligibility_verified':False,'award_verified':False,'note':'Prior checkpoint source observation, not an authenticated live cabinet check.'}
  previews.append(observation);projects[project]['v42_deadline_observation']=observation;actions[project]['v42_deadline_observation']=observation;queue[ident]['v42_deadline_observation']=observation
 budget={'id':'2145701/1','scope':'Budget estimate, KOS compressor control','original_deadline':'2026-11-13','mirror_deadline_msk':'2026-11-16 14:00','source':'https://t.me/s/siburholdingprocurement?before=927','mirror':'https://zakupki.kontur.ru/IS87179384','status':'BUDGET_ESTIMATE_NOT_ORDER','note':'Similar title on Energybase Nov20 not exact-ID linked. No extension or actual order inferred.'}
 exclusion={'id':'2139750/1','scope':'Gas safety emergency rescue and gas laboratory control, not analyzer supply','status':'ADJACENT_EXCLUDED_FROM_CORE','reported_deadline_msk':'2026-11-24 15:00','source':'https://t.me/s/siburholdingprocurement','mirror':'https://zakupki.kontur.ru/IS88434448'}
 assert queue[budget['id']]['budget_estimate_verified'] is True and exclusion['id'] not in queue
 for x in (projects['KOS_COMPRESSOR_CONTROL'],actions['KOS_COMPRESSOR_CONTROL'],queue[budget['id']]):x['v42_budget_observation']=budget
 actions['KOS_COMPRESSOR_CONTROL']['next_action_recommendation']='Уточнить повторную процедуру и текущую стадию после бюджетной оценки. Не считать срок зеркала подтвержденным продлением или заказом.'
 role={'company':'НПП ТЭК','inn':'7020037139','evidence_type':'self_reported_product_references_and_official_identity','contacts':'https://npptec.ru/contacts/','source':'https://www.npptec.ru/upload/iblock/08c/ts50ps6k0ihb8s2hd7s7203a7hxhdl1r.pdf','references':['Томскнефтехим 2004–2024','СибурТюменьГаз 2024','АГХК 2020–2023'],'note':'PDF text-only observation, screenshot unavailable. RemTEK reference not verified AUMA authorization, award, contract or service winner.'}
 actions['STG_AUMA_SERVICE']['v42_candidate_role']=role;projects['STG_AUMA_SERVICE']['v42_candidate_role']=role
 core=copy.deepcopy(c['price_comparator']['contracts']); assert len(core)==4;seen={x['register'] for x in core};adj=[]
 for ident,date,scope,price,kind in NEW_PRICES:
  assert ident not in seen;seen.add(ident);row={'register':ident,'date':date,'scope':scope,'price_rub':price,'supplier':None,'source':'https://zakupki.kontur.ru/D'+ident,'evidence_type':'secondary_eis_mirror','scope_group':kind}
  (core if kind=='core' else adj).append(row)
 assert len(core)==6 and len(adj)==1
 core_sum=sum(Decimal(x['price_rub']) for x in core);adj_sum=sum(Decimal(x['price_rub']) for x in adj)
 assert core_sum==Decimal('1173379.20') and adj_sum==Decimal('345845.60')
 overlay={'schema':'sibur_v42_checkpoint_observations_v1','as_of':'2026-11-16','basis':'Previously verified findings in sionika_v42_pending, not new live source calls','deadline_observations':previews,'budget_estimate':budget,'adjacent_exclusion':exclusion,'supplier_reference':role,'price_comparator':{'buyer':'АО СОВ-НКНХ','buyer_inn':'1651052730','core_contracts':core,'adjacent_contracts':adj,'core_sum_rub':str(core_sum),'adjacent_sum_rub':str(adj_sum),'supplier_names_verified':False,'boundary':'Secondary 223-FZ price comparators only, not direct NKNH/SIBUR awards, market total or current ownership proof'}}
 # Avoid circular digests: map points at queue filename; queue/actions bind final map digest.
 names=['sionika-v42-source-observations-v1.json','consolidated-project-map-v42.json','commercial-outcome-queue-v17.json','commercial-action-register-v36.json','consolidated-project-report-v42.md']
 assert not any((p/n).exists() for n in names),'V42 outputs already exist'
 oh=dump(p/names[0],overlay);m['schema']='sibur_consolidated_project_map_v42';m['as_of']='2026-11-16';m['prior_map_sha256']=EXPECTED['consolidated-project-map-v41.json'];m['source_artifacts'].update({names[0]:oh,'project-coverage-dashboard-v27.json':'0fd0e98b9a6214e1970b437e7d4729d246f78999f20e81a04441217bba284bff','project-coverage-dashboard-v28-post-storage-recovery.json':EXPECTED['project-coverage-dashboard-v28-post-storage-recovery.json']});m['coverage_dashboard']={'file':'project-coverage-dashboard-v28-post-storage-recovery.json','sha256':EXPECTED['project-coverage-dashboard-v28-post-storage-recovery.json'],'note':'Fresh post-recovery read-only observation, same frozen membership as V41'};m['sionika_v42_source_observations']={'file':names[0],'sha256':oh};m['commercial_outcome_queue']['file']=names[2]
 # Preserve exact frozen cohort membership and all previously established outcomes.
 assert [(x['project_id'],x['archive_publication_ids'],x['verified_award'],x['verified_market_value']) for x in m['projects']]==[(x['project_id'],x['archive_publication_ids'],x['verified_award'],x['verified_market_value']) for x in old['projects']]
 assert [(x['external_id'],x['signed_contract_verified'],x['award_verified']) for x in q['rows']]==[(x['external_id'],x['signed_contract_verified'],x['award_verified']) for x in oldq['rows']]
 assert [(x['project_id'],x['verified_award'],x['verified_order_value']) for x in a['rows']]==[(x['project_id'],x['verified_award'],x['verified_order_value']) for x in olda['rows']]
 mh=dump(p/names[1],m);q['schema']='sibur_outcome_research_queue_v17';q['source_map_sha256']=mh;q['prior_queue_sha256']=EXPECTED['commercial-outcome-queue-v16.json'];qh=dump(p/names[2],q);a['schema']='sibur_commercial_actions_v36';a['map_sha256']=mh;ah=dump(p/names[3],a)
 priorities=collections.Counter(x['priority_recommendation'] for x in m['projects']);co={x['name']:x for x in cov['cohorts']};allc,pr=co['all'],co['priority_union'];assert pr['total']==8244 and co['project_union']['total']==2659
 brief=['# СИБУР — карта проектов и коммерческий план Сионики','Срез 16.11.2026; рабочая редакция V42. Итоговая приёмка и подтверждение допуска не выполнены.','', '## Актуальное резюме V42',f"66 карточек: {priorities['P0']} P0, {priorities['P1']} P1, {priorities['P2']} P2; 30 меток площадок. 2659 уникальных публикаций в проектах, 2685 связей; приоритетное объединение 8244. Исторические разделы ниже сохранены; более ранние цифры и классификации не заменяют V42.",'','### Ближайшие действия, сроки по сохранённым наблюдениям','| Процедура | Проект | Срок МСК | Источник |','| --- | --- | --- | --- |']
 for ident,project,deadline,source in DEADLINES:brief.append(f"| {ident} | {projects[project]['name']} | {deadline} | {source} |")
 brief+=['','Сроки из архивированных проверок 16.11, не доказательство доступности подачи или квалификации. 2145701/1 — бюджетная оценка, не заказ; исходный срок 13.11, зеркало 16.11 14:00, точное продление не подтверждено. 2139750/1 — газоспасательные работы и лабораторный контроль, не поставка газоанализаторов; вне основного продуктового периметра.','', '### Покрытие корпуса после восстановления SSD', '| Показатель | Все публикации | Приоритет |','| --- | ---: | ---: |',f"| Уникальные публикации | {allc['total']} | {pr['total']} |",f"| Извлечён хотя бы один документ | {allc['extracted_any']} | {pr['extracted_any']} |",f"| Все поддерживаемые документы извлечены | {allc['all_supported_extracted']}/{allc['eligible']} | {pr['all_supported_extracted']}/{pr['eligible']} |",f"| Все известные документы, без неподтверждённых ссылок | {allc['all_known_no_unverified']} | {pr['all_known_no_unverified']} |",f"| Извлечено поддерживаемых URL | {allc['extracted_supported_urls']}/{allc['supported_urls']} | {pr['extracted_supported_urls']}/{pr['supported_urls']} |",f"| Индексированные процедуры | {allc['indexed']} | {pr['indexed']} |",'', 'Не доля полностью изученных тендеров или подтверждённых договоров. Техническое покрытие и коммерческое подтверждение разделены.','', '### Ценовые ориентиры 223-ФЗ — отдельный контур АО СОВ-НКНХ','| Реестровая запись | Дата | Предмет | Цена, руб. | Группа |','| --- | --- | --- | ---: | --- |']
 for x in core+adj:brief.append(f"| [{x['register']}]({x['source']}) | {x['date']} | {x['scope']} | {x['price_rub']} | {'Смежный' if x in adj else 'Профильный'} |")
 brief += ['',f'Шесть профильных сравнительных цен: {core_sum} руб.; отдельно один смежный клапан: {adj_sum} руб. Вторичное зеркало ЕИС; поставщики скрыты, первичные документы и актуальная структура собственности не подтверждены. Не суммировать с прямыми расходами СИБУРа.', '', 'НПП ТЭК, ИНН 7020037139: заявленные производителем референсы RemTEK на ТНХ, СТГ и АГХК. Контакты: https://npptec.ru/contacts/ . Это кандидат кооперации, не доказательство статуса авторизованного сервиса AUMA или победы.', '', '### Полная карта V42', '| Приоритет | Проект | Площадка | Публикации-кандидаты | Последняя известная стадия |','| --- | --- | --- | ---: | --- |']
 for x in m['projects']:
  vals=[x['priority_recommendation'],x['name'],x['site_label'],str(len(x['archive_publication_ids'])),str(x['stage_as_reported'])]
  brief.append('| '+' | '.join(v.replace('|','/').replace('\n',' ') for v in vals)+' |')
 brief+=['','Источники V42:','- '+names[0]+' — '+oh,'- '+names[1]+' — '+mh,'- '+names[2]+' — '+qh,'- '+names[3]+' — '+ah,'- project-coverage-dashboard-v28-post-storage-recovery.json — '+EXPECTED['project-coverage-dashboard-v28-post-storage-recovery.json'],'','---','','## Историческая детализация V41 и более ранних редакций','', (p/'consolidated-project-report-v41.md').read_text()]
 with (p/names[4]).open('x') as f:f.write('\n'.join(brief)+'\n')
 print(json.dumps({'artifacts':{n:sha(p/n) for n in names},'projects':len(projects),'priority_counts':dict(priorities),'queue_rows':len(queue),'core_prices':len(core),'core_sum':str(core_sum),'adjacent_sum':str(adj_sum),'strict_awards_unchanged':True},ensure_ascii=False))

if __name__=='__main__':main()
