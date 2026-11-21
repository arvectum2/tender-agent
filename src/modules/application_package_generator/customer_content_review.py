"""Independent, bounded structural review of our generated commercial drafts.

Not a semantic confidentiality certificate, independent human approval or submission gate.
Never applies to arbitrary uploaded customer forms.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from decimal import ROUND_HALF_UP, Decimal

from docx import Document

from .customer_draft_export import OUTPUT

_INTERNAL_MARKERS = re.compile(
    r'\b(?:себестоимост\w*|маржинальност\w*|марж[аиуей]\w*|'
    r'внутренн\w*\s+(?:расч[её]т\w*|аналитик\w*|экономик\w*)|'
    r'cost\s*price|internal\s+(?:cost|margin|profit|scenario|analysis)|'
    r'target_profit_rub|external_direct_rub|economic_profit_rub|price-scenario\.json|'
    r'private-bid-review-v1|company_profile_fact)\b', re.IGNORECASE
)


def _review_text(text):
    if any(unicodedata.category(c) in ('Cc', 'Cf', 'Cs') for c in text):
        raise ValueError('Unsupported control characters in customer draft wording')
    normalized = unicodedata.normalize('NFKC', text).casefold()
    if _INTERNAL_MARKERS.search(normalized):
        raise ValueError('Known internal marker in customer draft wording')
    if re.search(r'\{\{[^}]+\}\}', normalized):
        raise ValueError('Unresolved placeholder in customer draft wording')


def _money(value):
    return format(Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), 'f')


def _expected_doc(kind, terms):
    doc = Document()
    doc.add_heading('ПРОЕКТ — НЕ ПОДПИСАНО', 0)
    doc.add_heading('Проект ценового предложения' if kind == 'price_offer' else 'Проект деклараций участника', 1)
    doc.add_paragraph('Закупка: ' + terms.procurement_ref)
    if kind == 'price_offer':
        doc.add_paragraph('Лот: ' + terms.lot_ref)
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        names = ('Наименование', 'Количество', 'Ед.', 'Цена за ед., руб.', 'Сумма, руб.')
        for cell, name in zip(table.rows[0].cells, names, strict=True):
            cell.text = name
        for line in terms.lines:
            _review_text(line.description)
            _review_text(line.unit)
            values = (line.description, line.quantity, line.unit, _money(line.gross_unit_price_rub),
                      _money(Decimal(line.quantity) * Decimal(line.gross_unit_price_rub)))
            for cell, value in zip(table.add_row().cells, values, strict=True):
                cell.text = value
        doc.add_paragraph('Итого: ' + _money(terms.total_rub) + ' руб.')
        _review_text(terms.vat_basis)
        tax = ('НДС: ' + _money(terms.vat_amount_rub) + ' руб., ставка ' + str(terms.vat_rate_percent) + '%'
               if terms.vat_mode == 'VAT_EXPLICIT' else 'Без НДС')
        doc.add_paragraph(tax + '. Основание: ' + terms.vat_basis)
        doc.add_paragraph('Срок действия проекта: ' + terms.valid_through.isoformat())
    elif kind == 'declarations':
        for statement in terms.statements:
            _review_text(statement.exact_wording)
            doc.add_paragraph(statement.exact_wording)
            doc.add_paragraph('Ответ проекта: подтверждено владельцем для проверки.')
    else:
        raise ValueError('Unknown customer draft type')
    doc.add_paragraph('Подпись: __________________')
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def _parts(raw):
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Customer DOCX exceeds review limit')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if (len(infos) > 64 or len(names) != len(set(names))
                or sum(i.file_size for i in infos) > 8 * 1024 * 1024
                or any(i.flag_bits & 1 for i in infos)):
            raise ValueError('Unexpected customer DOCX package')
        return {i.filename: z.read(i) for i in infos}


def review_customer_export(raw, *, selection, offer_terms=None, declaration_terms=None):
    """Compare all inner OOXML parts with an independently composed exact expected document."""
    terms = {'price_offer': offer_terms, 'declarations': declaration_terms}
    if not selection or len(selection) != len(set(selection)) or set(selection) - set(terms):
        raise ValueError('Unknown customer draft selection')
    files = _parts(raw)
    if set(files) != {OUTPUT[key] for key in selection}:
        raise ValueError('Unexpected customer draft archive content')
    for key in selection:
        if terms[key] is None:
            raise ValueError('Retained customer draft terms missing')
        if _parts(files[OUTPUT[key]]) != _parts(_expected_doc(key, terms[key])):
            raise ValueError('Customer document differs from independently reconstructed content')
    return {'status': 'EXACT_GENERATED_CONTENT_MATCH', 'documents': sorted(selection),
            'semantic_confidentiality_verified': False, 'independent_human_review': False,
            'application_ready': False, 'submission_allowed': False}
