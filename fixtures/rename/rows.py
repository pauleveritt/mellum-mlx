def fetch_rows(source):
    return [tuple(line.split("|")) for line in source.splitlines() if line]
