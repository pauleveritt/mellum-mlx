def render_rows(rows):
    return [",".join(str(v) for v in r) for r in rows]
