"""Source-aware action wording for training-service procurement reviews.

This helper produces questions for verification, not geographic source facts.
"""
from __future__ import annotations


def build_training_location_action(location: str | None, training_format: str | None) -> str:
    if location and location.strip():
        # Echo only bounded wording from the original source, never a default city.
        source_location = " ".join(location.split()).strip(" .;,")[:180].rstrip(" .;,")
        return (
            "Проверить возможность очной части по месту оказания услуг, "
            f"указанному в ТЗ ({source_location}), и дистанционной части "
            "в требуемом формате."
        )
    if training_format:
        return (
            "Уточнить у заказчика место проведения очной части и подтвердить "
            "требования к дистанционному формату обучения."
        )
    return "Подтвердить реальный формат оказания услуг и локацию исполнения."
