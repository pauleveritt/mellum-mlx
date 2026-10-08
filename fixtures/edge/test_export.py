from export import export_csv


def test_export_without_totals():
    assert export_csv([[1, 2], [3, 4]]) == "1,2\n3,4"


def test_export_appends_totals_row():
    assert export_csv([[1, 2], [3, 4]], totals=True) == "1,2\n3,4\n4,6"
