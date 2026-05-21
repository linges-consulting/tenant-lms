from weasyprint import HTML


def render_certificate_pdf(html_template: str, variables: dict) -> bytes:
    """Render HTML template to a single-page landscape PDF using WeasyPrint."""
    html = html_template
    for key, value in variables.items():
        html = html.replace(f"{{{{{key}}}}}", str(value or ""))

    landscape_css = "<style>@page { size: A4 landscape; margin: 1cm; }</style>"
    if "@page" not in html:
        if "<head>" in html:
            html = html.replace("<head>", f"<head>{landscape_css}", 1)
        else:
            html = landscape_css + html

    return HTML(string=html).write_pdf()
