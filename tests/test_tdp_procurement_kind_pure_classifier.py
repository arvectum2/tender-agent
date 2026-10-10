"""Pure classifier is callable without operator upload/runtime initialization."""

from src.modules.tender_operator_agent_demo.procurement_kind_classifier import (
    infer_procurement_kind,
)
from src.modules.tender_operator_agent_demo.upload_service_legacy import (
    _infer_procurement_kind,
)


def test_old_operator_function_is_thin_compatibility_facade():
    samples = (
        (),
        ("",),
        ("Черновик Черновик",),
        ("Оказание услуг по разработке сайта",),
        ("Поставка серверного оборудования",),
        ("Выполнение работ по ремонту помещения",),
        ("Доработка информационной системы с интеграцией в ЕРН",),
        ("Неисключительные права на программное обеспечение",),
    )
    for sample in samples:
        assert _infer_procurement_kind(*sample) == infer_procurement_kind(*sample)


def test_unsupported_ambiguous_text_not_source_verified():
    assert infer_procurement_kind("данные отсутствуют") == "generic"
    assert infer_procurement_kind() == "generic"
