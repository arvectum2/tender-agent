from scripts.research.build_sibur_switchgear_retrofit import classify


def test_retrofit_and_protection():
    assert classify("Ретрофит ячеек","РУ-6 кВ")=="direct_switchgear_retrofit_review"
    assert classify("РЗА","Замена реле на микропроцессорные терминалы")=="direct_switchgear_retrofit_review"
    assert classify("Ретрофит КРУ","")=="direct_switchgear_retrofit_review"
    assert classify("Ретрофит микропроцессорных блоков","ретрофит микропроцессорных блоков SIMOREG")=="other_retrofit"
    assert classify("Ретрофит","")=="ambiguous_retrofit_review"
    assert classify("Поставка КРУ","") is None


def test_related_not_direct():
    assert classify("Техническое перевооружение","монтаж КРУ-10 кВ")=="related_electrical_modernization_review"
    assert classify("Замена силовых трансформаторов","ЭМР, РЗА")=="related_electrical_modernization_review"
