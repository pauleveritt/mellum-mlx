def column_totals(rows):
    if not rows:
        return []
    return [sum(r[i] for r in rows) for i in range(len(rows[0]))]
