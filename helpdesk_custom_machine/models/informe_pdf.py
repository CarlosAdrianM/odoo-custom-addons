"""PDF del informe de reparación, con ReportLab (dependencia propia de Odoo).

No se usa un informe QWeb porque en el servidor no está instalado wkhtmltopdf
y se decidió no instalar nada nuevo en producción.
"""
import base64
import io
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_DEJAVU = "/usr/share/fonts/truetype/dejavu"
GRIS = colors.HexColor("#5f6368")
LINEA = colors.HexColor("#c9cdd2")
TINTA = colors.HexColor("#1f2933")


def _fuentes():
    """DejaVu si está en el sistema (cubre cualquier carácter); si no, Helvetica."""
    normal, negrita = os.path.join(_DEJAVU, "DejaVuSans.ttf"), os.path.join(_DEJAVU, "DejaVuSans-Bold.ttf")
    if os.path.isfile(normal) and os.path.isfile(negrita):
        if "InformeSans" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("InformeSans", normal))
            pdfmetrics.registerFont(TTFont("InformeSans-Bold", negrita))
        return "InformeSans", "InformeSans-Bold"
    return "Helvetica", "Helvetica-Bold"


def _parrafo(texto, estilo):
    return Paragraph(escape((texto or "").strip()).replace("\n", "<br/>"), estilo)


def _logo(logo_b64, ancho_max=55 * mm, alto_max=22 * mm):
    if not logo_b64:
        return None
    try:
        datos = base64.b64decode(logo_b64)
        ancho, alto = ImageReader(io.BytesIO(datos)).getSize()
    except Exception:
        return None  # p. ej. un SVG: el informe sale sin logo en vez de fallar
    escala = min(ancho_max / ancho, alto_max / alto)
    imagen = Image(io.BytesIO(datos), width=ancho * escala, height=alto * escala)
    imagen.hAlign = "LEFT"
    return imagen


def generar(datos):
    """Devuelve los bytes del PDF.

    ``datos``: logo (base64 o None), numero, fecha, filas (lista de pares
    etiqueta/valor), secciones (lista de pares título/texto; las vacías se
    omiten) y pie (lista de líneas con los datos de la empresa).
    """
    normal, negrita = _fuentes()
    base = ParagraphStyle("base", fontName=normal, fontSize=10, leading=14.5, textColor=TINTA)
    titulo = ParagraphStyle("titulo", parent=base, fontName=negrita, fontSize=17, leading=21, alignment=TA_RIGHT)
    subtitulo = ParagraphStyle("subtitulo", parent=base, fontSize=9.5, textColor=GRIS, alignment=TA_RIGHT)
    etiqueta = ParagraphStyle("etiqueta", parent=base, fontSize=8.5, leading=12, textColor=GRIS)
    valor = ParagraphStyle("valor", parent=base, fontName=negrita, fontSize=10, leading=13)
    seccion = ParagraphStyle("seccion", parent=base, fontName=negrita, fontSize=11, leading=14, spaceBefore=13, spaceAfter=4)

    pie = datos.get("pie") or []

    def dibujar_pie(lienzo, documento):
        lienzo.saveState()
        lienzo.setStrokeColor(LINEA)
        lienzo.setLineWidth(0.5)
        lienzo.line(documento.leftMargin, 20 * mm, A4[0] - documento.rightMargin, 20 * mm)
        lienzo.setFont(normal, 7.5)
        lienzo.setFillColor(GRIS)
        y = 16 * mm
        for linea in pie[:3]:
            lienzo.drawCentredString(A4[0] / 2, y, linea)
            y -= 3.6 * mm
        lienzo.drawRightString(A4[0] - documento.rightMargin, 7 * mm, "Página %d" % documento.page)
        lienzo.restoreState()

    salida = io.BytesIO()
    documento = SimpleDocTemplate(
        salida,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=16 * mm,
        bottomMargin=27 * mm,
        title="Informe de reparación %s" % (datos.get("numero") or ""),
        author=(pie[0] if pie else ""),
    )
    ancho = documento.width

    cabecera_derecha = [
        Paragraph("Informe de reparación", titulo),
        _parrafo("%s · %s" % (datos.get("numero") or "", datos.get("fecha") or ""), subtitulo),
    ]
    cabecera = Table([[_logo(datos.get("logo")) or "", cabecera_derecha]], colWidths=[ancho * 0.45, ancho * 0.55])
    cabecera.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, TINTA),
    ]))
    flujo = [cabecera, Spacer(1, 7 * mm)]

    filas = [(e, v) for e, v in (datos.get("filas") or []) if v]
    if filas:
        if len(filas) % 2:
            filas.append(("", ""))
        celdas = []
        for i in range(0, len(filas), 2):
            celdas.append([
                [_parrafo(filas[i][0], etiqueta), _parrafo(filas[i][1], valor)],
                [_parrafo(filas[i + 1][0], etiqueta), _parrafo(filas[i + 1][1], valor)],
            ])
        tabla = Table(celdas, colWidths=[ancho / 2, ancho / 2])
        tabla.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, LINEA),
        ]))
        flujo += [tabla, Spacer(1, 2 * mm)]

    for nombre, texto in datos.get("secciones") or []:
        if (texto or "").strip():
            flujo += [Paragraph(escape(nombre), seccion), _parrafo(texto, base)]

    documento.build(flujo, onFirstPage=dibujar_pie, onLaterPages=dibujar_pie)
    return salida.getvalue()
