# Legacy exporter kept for an old integration. Do not change.
def export_csv_legacy(rows):
    return "\r\n".join(";".join(str(v) for v in r) for r in rows)
