from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    memo: str
    amount: int


def entries_from_lines(lines):
    out = []
    for line in lines:
        memo, amount = line.rsplit(",", 1)
        out.append(Entry(memo.strip(), int(amount)))
    return out
