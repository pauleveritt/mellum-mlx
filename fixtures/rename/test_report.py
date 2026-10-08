from report import report


def test_report_joins_cells():
    assert report("a|b\nc|d") == "a b\nc d"
