import pytest
from app.comparison import compare, normalize_po
from app.schemas import Extracted, Item, decimal_value


def doc(po="001132536", qty="1.00", uom="CS", confidence=0.99, code=""):
    return Extracted(po=po, po_confidence=confidence,
                     items=[Item(code=code, qty=qty, uom=uom, confidence=confidence)])


def test_sample_same_quantity_in_cs():
    result = compare(doc("1132536", "1"), doc("1132536", "1.00"))
    assert (result.status, result.po_status, result.qty_status) == ("match", "match", "match")


@pytest.mark.parametrize("left,right,expected", [
    (doc(po="00012"), doc(po="12"), "mismatch"),
    (doc(qty="1"), doc(qty="2"), "mismatch"),
    (doc(uom="MU", qty="5"), doc(uom="CS", qty="1"), "unit_mismatch"),
    (doc(po=""), doc(), "review"),
    (doc(confidence=0.3), doc(), "review"),
    (doc(qty=""), doc(), "review"),
    (doc(qty="NaN"), doc(), "review"),
    (doc(code="A"), doc(code="B"), "review"),
])
def test_unsafe_values_never_pass(left, right, expected):
    assert compare(left, right).status == expected


def test_decimal_exactness_and_po_formatting():
    assert compare(doc(po=" ab - 001 ", qty="1,000.10"), doc(po="AB001", qty="1000.100")).status == "match"
    assert normalize_po("000-12") == "00012"
    assert decimal_value("1,00") is None
    assert decimal_value("-1") is None
    assert decimal_value("Infinity") is None


def test_multiple_items_reordered_by_code_not_total():
    left, right = doc(), doc()
    left.items = [Item(code="A", qty="2", uom="CS", confidence=.99), Item(code="B", qty="3", uom="CS", confidence=.99)]
    right.items = list(reversed([item.model_copy() for item in left.items]))
    assert compare(left, right).status == "match"
    right.items[0].qty = "2"
    right.items[1].qty = "3"
    assert compare(left, right).status == "mismatch"
    right.items[1].code = "B"
    assert compare(left, right).status == "review"


def test_manual_confirmation_does_not_override_unit_or_identity_rules():
    assert compare(doc(confidence=0), doc(confidence=0), reviewed=True).status == "match"
    assert compare(doc(uom="MU"), doc(), reviewed=True).status == "unit_mismatch"
    assert compare(doc(code="A"), doc(code="B"), reviewed=True).status == "review"


def test_warnings_block_automatic_match():
    left = doc()
    left.warnings = ["ambiguous table"]
    assert compare(left, doc()).status == "review"
