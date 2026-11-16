from scripts.research.build_sibur_project_channels import BRANDS, PROJECTS, matches


def test_agpz_not_aghk():
    assert set(matches("АГПЗ. Шкаф КРУ 10 кВ", PROJECTS)) == {"AGPZ"}
    assert set(matches("АГХК, ОЗХ, трансформаторы тока", PROJECTS)) == {"AGHK"}
    assert set(matches("АГПЗ. сети АГХК", PROJECTS)) == {"AGPZ","AGHK"}


def test_project_and_brand_spelling():
    assert set(matches("НПГ&СПР; ДГП-2; ЭП-600", PROJECTS)) == {"NPG_SPR","DGP2","EP600"}
    assert set(matches("Rosemount, ABB, Endress+Hauser", BRANDS)) == {"Emerson/Rosemount","ABB","Endress+Hauser"}
