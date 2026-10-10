"""Source-aware action wording for training-service procurement reviews.

This helper produces questions for verification, not geographic source facts.
"""
from __future__ import annotations


def build_training_location_action(location: str | None, training_format: str | None) -> str:
    if location:
        return (
            "Проверить возможность очной части по месту оказания услуг, "
            "указанному в ТЗ, и дистанционной части в требуемом формате."
        )
    if training_format:
        return (
            "Уточнить у заказчика место проведения очной части и подтвердить "
            "требования к дистанционному формату обучения."
        )
    return "Подтвердить реальный формат оказания услуг и локацию исполнения."
