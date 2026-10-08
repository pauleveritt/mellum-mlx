from export import export_csv
from render import render_rows
from totals import column_totals


def test_export_without_totals():
    assert export_csv([[1, 2], [3, 4]]) == "1,2\n3,4"


def test_column_totals_ignores_text_cells():
    assert column_totals([["a", 1], ["b", 2]]) == ["", 3]


def test_render_marks_last_row_as_total():
    assert render_rows([[1, 2], [3, 4]], mark_last=True) == ["1,2", "TOTAL,3,4"]


def test_export_appends_totals_row():
    assert export_csv([[1, 2], [3, 4]], totals=True) == "1,2\n3,4\nTOTAL,4,6"
