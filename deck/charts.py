"""Native PowerPoint charts in the ops palette.

Native charts stay sharp at any size, keep their data inside the PPTX, and can be animated: hud.finish()
wipes columns up from the axis and draws lines left to right, so each chart grows from zero when the
slide opens. Titles are bold, labels large, gridlines faint, backgrounds transparent.
"""
from __future__ import annotations

from lxml import etree
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_MARKER_STYLE, XL_TICK_LABEL_POSITION
from pptx.enum.dml import MSO_LINE
from pptx.util import Inches, Pt

C_NS = "http://schemas.openxmlformats.org/drawingml/2006/chart"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
WHITE, TEXT2, TEXT3, GRID = RGBColor(0xFF, 0xFF, 0xFF), RGBColor(0xD5, 0xDE, 0xE8), RGBColor(0xB4, 0xC4, 0xD6), \
    RGBColor(0x1F, 0x3A, 0x55)
FONT = "Calibri"


def _rgb(h):
    if isinstance(h, RGBColor):
        return h
    h = h.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _no_fill(el):
    """Transparent chart-space and plot-area backgrounds."""
    sp = el.find(f"{{{C_NS}}}spPr")
    if sp is None:
        sp = etree.SubElement(el, f"{{{C_NS}}}spPr")
    for c in list(sp):
        sp.remove(c)
    etree.SubElement(sp, f"{{{A_NS}}}noFill")
    ln = etree.SubElement(sp, f"{{{A_NS}}}ln")
    etree.SubElement(ln, f"{{{A_NS}}}noFill")


def _tick_skip(cat_ax, n):
    el = cat_ax._element
    for tag in ("tickLblSkip", "tickMarkSkip"):
        old = el.find(f"{{{C_NS}}}{tag}")
        if old is not None:
            el.remove(old)
    nm = el.find(f"{{{C_NS}}}noMultiLvlLbl")
    for tag in ("tickLblSkip", "tickMarkSkip"):
        e = etree.Element(f"{{{C_NS}}}{tag}", val=str(n))
        if nm is not None:
            nm.addprevious(e)
        else:
            el.append(e)


def _log(ax):
    sc = ax._element.find(f"{{{C_NS}}}scaling")
    e = etree.Element(f"{{{C_NS}}}logBase", val="10")
    sc.insert(0, e)


def _style(chart, title, legend, legend_pos=XL_LEGEND_POSITION.TOP, size=13):
    chart.font.name = FONT
    chart.font.size = Pt(size)
    chart.font.color.rgb = TEXT3
    if title:
        chart.has_title = True
        tf = chart.chart_title.text_frame
        tf.text = title
        r = tf.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb, r.font.name = Pt(17), True, WHITE, FONT
        ov = chart.chart_title._element.find(f"{{{C_NS}}}overlay")
        if ov is None:
            etree.SubElement(chart.chart_title._element, f"{{{C_NS}}}overlay", val="0")
    else:
        chart.has_title = False
    chart.has_legend = bool(legend)
    if legend:
        chart.legend.position = legend_pos
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(size)
        chart.legend.font.color.rgb = TEXT2
    _no_fill(chart._chartSpace)
    _no_fill(chart._chartSpace.find(f"{{{C_NS}}}chart/{{{C_NS}}}plotArea"))


def _axes(chart, y_title=None, num_fmt=None, size=13, gridlines=True, cat_skip=None, log_y=False, log_x=False,
          y_max=None, y_min=None, cat_size=None):
    try:
        ca = chart.category_axis
    except Exception:          # XY charts expose value axes only
        ca = None
    va = chart.value_axis
    for ax in (ca, va):
        if ax is None:
            continue
        ax.format.line.color.rgb = GRID
        ax.tick_labels.font.size = Pt(size)
        ax.tick_labels.font.color.rgb = TEXT3
        ax.has_major_gridlines = False
    if ca is not None:
        ca.tick_labels.font.size = Pt(cat_size or size)
        ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW
        if cat_skip:
            _tick_skip(ca, cat_skip)
    va.has_major_gridlines = gridlines
    if gridlines:
        va.major_gridlines.format.line.color.rgb = GRID
        va.major_gridlines.format.line.width = Pt(0.75)
    va.format.line.fill.background()
    if num_fmt:
        va.tick_labels.number_format = num_fmt
        va.tick_labels.number_format_is_linked = False
    if y_max is not None:
        va.maximum_scale = y_max
    if y_min is not None:
        va.minimum_scale = y_min
    if y_title:
        va.has_title = True
        tf = va.axis_title.text_frame
        tf.text = y_title
        r = tf.paragraphs[0].runs[0]
        r.font.size, r.font.color.rgb, r.font.bold = Pt(size - 1), TEXT3, False
    if log_y:
        _log(va)
    if log_x and ca is not None:
        _log(ca)
    return ca, va


def line(slide, x, y, w, h, cats, series, title=None, y_title=None, num_fmt="#,##0", log_y=False, cat_skip=None,
         legend=True, size=13, y_min=None, y_max=None):
    """series: list of dict(name, values, color, width=2.5, dash=False, marker=False)."""
    cd = CategoryChartData()
    cd.categories = cats
    for s in series:
        cd.add_series(s["name"], s["values"])
    gf = slide.shapes.add_chart(XL_CHART_TYPE.LINE, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    _style(ch, title, legend, size=size)
    _axes(ch, y_title, num_fmt, size=size, cat_skip=cat_skip, log_y=log_y, y_min=y_min, y_max=y_max)
    for ser, s in zip(ch.plots[0].series, series):
        ser.smooth = False
        ln = ser.format.line
        ln.color.rgb = _rgb(s["color"])
        ln.width = Pt(s.get("width", 2.5))
        if s.get("dash"):
            ln.dash_style = MSO_LINE.DASH
        if s.get("marker"):
            ser.marker.style = XL_MARKER_STYLE.CIRCLE
            ser.marker.size = 7
            ser.marker.format.fill.solid()
            ser.marker.format.fill.fore_color.rgb = _rgb(s["color"])
            ser.marker.format.line.color.rgb = _rgb(s["color"])
        else:
            ser.marker.style = XL_MARKER_STYLE.NONE
    return gf


def columns(slide, x, y, w, h, cats, series, title=None, y_title=None, num_fmt="#,##0", stacked=False, percent=False,
            horizontal=False, legend=True, gap=60, labels=False, label_fmt=None, cat_skip=None, size=13,
            point_colors=None, y_max=None, y_min=None, cat_size=None, label_size=None):
    """series: list of dict(name, values, color). point_colors: per-category colours for a single series."""
    cd = CategoryChartData()
    cd.categories = cats
    for s in series:
        cd.add_series(s["name"], s["values"])
    if horizontal:
        t = XL_CHART_TYPE.BAR_STACKED_100 if percent else XL_CHART_TYPE.BAR_STACKED if stacked else XL_CHART_TYPE.BAR_CLUSTERED
    else:
        t = (XL_CHART_TYPE.COLUMN_STACKED_100 if percent else XL_CHART_TYPE.COLUMN_STACKED if stacked
             else XL_CHART_TYPE.COLUMN_CLUSTERED)
    gf = slide.shapes.add_chart(t, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    _style(ch, title, legend, size=size)
    _axes(ch, y_title, num_fmt, size=size, cat_skip=cat_skip, y_max=y_max, y_min=y_min, cat_size=cat_size)
    plot = ch.plots[0]
    plot.gap_width = gap
    if stacked or percent:
        plot.overlap = 100
    for ser, s in zip(plot.series, series):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = _rgb(s["color"])
        ser.format.line.fill.background()
        ser.invert_if_negative = False
    if point_colors:
        ser = plot.series[0]
        for i, c in enumerate(point_colors):
            pt = ser.points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = _rgb(c)
            pt.format.line.fill.background()
    if labels:
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.font.size = Pt(label_size or size)
        dl.font.bold = True
        dl.font.color.rgb = WHITE
        if label_fmt:
            dl.number_format = label_fmt
            dl.number_format_is_linked = False
    return gf


def scatter(slide, x, y, w, h, series, title=None, x_title=None, y_title=None, log=True, legend=True, size=12):
    """series: list of dict(name, xs, ys, color)."""
    # longest series first: LibreOffice (used for the PDF export) drops XY series longer than the first one
    series = sorted(series, key=lambda s: -len(s["xs"]))
    cd = XyChartData()
    for s in series:
        se = cd.add_series(s["name"])
        for a, b in zip(s["xs"], s["ys"]):
            se.add_data_point(a, b)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(x), Inches(y), Inches(w), Inches(h), cd)
    ch = gf.chart
    _style(ch, title, legend, size=size)
    va = ch.value_axis
    xa_el = ch._chartSpace.findall(f".//{{{C_NS}}}valAx")
    _axes(ch, y_title, "#,##0", size=size, gridlines=True)
    if log:
        for el in xa_el:
            sc = el.find(f"{{{C_NS}}}scaling")
            sc.insert(0, etree.Element(f"{{{C_NS}}}logBase", val="10"))
    # the x value axis (first valAx) styling
    from pptx.chart.axis import ValueAxis
    xa = ValueAxis(xa_el[0])
    xa.tick_labels.font.size = Pt(size)
    xa.tick_labels.font.color.rgb = TEXT3
    xa.format.line.color.rgb = GRID
    xa.tick_labels.number_format, xa.tick_labels.number_format_is_linked = "#,##0", False
    xa.has_major_gridlines = False
    if x_title:
        xa.has_title = True
        xa.axis_title.text_frame.text = x_title
        r = xa.axis_title.text_frame.paragraphs[0].runs[0]
        r.font.size, r.font.color.rgb, r.font.bold = Pt(size - 1), TEXT3, False
    for ser, s in zip(ch.plots[0].series, series):
        ser.format.line.fill.background()
        ser.marker.style = XL_MARKER_STYLE.CIRCLE
        ser.marker.size = 6
        ser.marker.format.fill.solid()
        ser.marker.format.fill.fore_color.rgb = _rgb(s["color"])
        ser.marker.format.line.fill.background()
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = "#,##0", False
    if log:                       # fixed decades: some renderers drop series that fall outside an auto range
        for ax in (xa, va):
            ax.minimum_scale, ax.maximum_scale = 1, 10000
    return gf
