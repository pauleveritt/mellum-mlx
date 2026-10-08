from rows import fetch_rows


def report(source):
    return "\n".join(" ".join(r) for r in fetch_rows(source))
