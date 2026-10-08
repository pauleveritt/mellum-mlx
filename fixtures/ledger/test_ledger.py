from ledger import Entry, entries_from_lines


def test_parses_lines():
    assert entries_from_lines(["coffee, -3", "pay, 10"]) == [
        Entry("coffee", -3),
        Entry("pay", 10),
    ]
