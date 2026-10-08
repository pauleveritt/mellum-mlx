from render import render_rows


def export_csv(rows):
    return "\n".join(render_rows(rows))
