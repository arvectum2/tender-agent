"""Leaf XML values must not fall back to a parent via falsy Element truthiness."""

from __future__ import annotations

from xml.etree import ElementTree as ET

from src.modules.tender_operator_agent_demo.upload_service import _structured_quantity


def test_nested_leaf_value_selected_explicitly():
    item = ET.fromstring("<item><quantity><value>17</value><unit>not a number</unit></quantity></item>")
    assert _structured_quantity(item) == "17"


def test_parent_quantity_text_selected_if_no_value():
    item = ET.fromstring("<item><quantity>5</quantity></item>")
    assert _structured_quantity(item) == "5"
