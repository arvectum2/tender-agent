"""Substrings of ordinary Russian words cannot spoof procurement integration."""

from src.modules.tender_operator_agent_demo.upload_service_legacy import _infer_procurement_kind


def test_chernovik_repetition_does_not_imply_ern_integration():
    assert _infer_procurement_kind("Черновик Черновик") == "generic"
    assert _infer_procurement_kind("Черновик предложения об оказании услуг") == "services"


def test_real_ern_abbreviation_still_counts_as_integration():
    assert _infer_procurement_kind("Единый реестр населения ЕРН, обмен данными с ЕРН") == "integration"


def test_software_work_with_real_ern_classifies_as_mixed():
    assert _infer_procurement_kind(
        "Доработка информационной системы с интеграцией в ЕРН"
    ) == "mixed"
