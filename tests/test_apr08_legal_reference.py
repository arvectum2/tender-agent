from src.modules.tender_operator_agent_demo.evidence_legal_reference import (
    extract_customer_legal_references,
)


def test_exact_reference_offsets_and_deduplication():
    text = ('ст. 45 Закона № 44-ФЗ, постановления Правительства РФ от 08.11.2013 № 1005; '
            'статьи 45 Федерального закона № 44-ФЗ; статьи 95 Федерального закона № 44-ФЗ')
    refs = extract_customer_legal_references(text)
    assert len(refs) == 3
    assert refs[0]['article'] == '45' and refs[1]['stated_number'] == '1005' and refs[2]['article'] == '95'
    for r in refs:
        assert text[r['char_start_in_excerpt']:r['char_end_in_excerpt']] == r['literal']
        assert not r['statute_text_verified'] and not r['applicability_verified']


def test_distant_or_unpaired_numbers_are_not_article_references():
    assert extract_customer_legal_references('Предмет закупки: 44-ФЗ. Пункт 45. Оплата 10 дней. Статья 37 ГК РФ.') == []
