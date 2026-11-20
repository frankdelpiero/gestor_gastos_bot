"""Crea/actualiza la hoja de Google Sheets (idempotente): Registro, Resumen, Categorías, _Meta y Dashboard.

Uso:  python scripts/setup_sheet.py
Lee SPREADSHEET_ID y GOOGLE_SERVICE_ACCOUNT_JSON del entorno (la hoja debe estar compartida
con el email de la cuenta de servicio como Editor). Los datos del Registro nunca se tocan;
el Dashboard (solo fórmulas) se reconstruye en cada ejecución.

Nota: la API de Sheets siempre interpreta las fórmulas en sintaxis inglesa (comas, nombres EN),
sea cual sea la configuración regional de la hoja.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gastos_bot.categories import DEFAULT_RULES  # noqa: E402
from gastos_bot.sheets.client import open_spreadsheet  # noqa: E402
from gastos_bot.sheets.repository import CATEGORIAS, HEADERS, META, REGISTRO  # noqa: E402

RESUMEN, DASHBOARD = "Resumen", "Dashboard"
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
EUR = {"type": "NUMBER", "pattern": '#,##0.00 "€"'}
BLUE, GREY, WHITE = {"red": 0.10, "green": 0.34, "blue": 0.62}, {"red": 0.94, "green": 0.95, "blue": 0.97}, {"red": 1, "green": 1, "blue": 1}


def get_or_create(ss, title, rows=1000, cols=26):
    try:
        return ss.worksheet(title)
    except Exception:  # noqa: BLE001
        return ss.add_worksheet(title, rows, cols)


def rng(sheet_id, r0, r1, c0, c1):
    return {"sheetId": sheet_id, "startRowIndex": r0, "endRowIndex": r1, "startColumnIndex": c0, "endColumnIndex": c1}


def list_rule(sheet_id, r0, r1, c0, c1, values=None, source=None):
    cond = {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": str(v)} for v in values]} if values else \
        {"type": "ONE_OF_RANGE", "values": [{"userEnteredValue": source}]}
    return {"setDataValidation": {"range": rng(sheet_id, r0, r1, c0, c1),
                                  "rule": {"condition": cond, "showCustomUi": True, "strict": True}}}


def fmt(sheet_id, r0, r1, c0, c1, number=None, bold=None, bg=None, fg=None, size=None, align=None):
    cell, fields = {}, []
    if number:
        cell["numberFormat"] = number; fields.append("userEnteredFormat.numberFormat")
    tf = {}
    if bold is not None: tf["bold"] = bold
    if fg: tf["foregroundColor"] = fg
    if size: tf["fontSize"] = size
    if tf:
        cell["textFormat"] = tf; fields.append("userEnteredFormat.textFormat")
    if bg:
        cell["backgroundColor"] = bg; fields.append("userEnteredFormat.backgroundColor")
    if align:
        cell["horizontalAlignment"] = align; fields.append("userEnteredFormat.horizontalAlignment")
    return {"repeatCell": {"range": rng(sheet_id, r0, r1, c0, c1), "cell": {"userEnteredFormat": cell},
                           "fields": ",".join(fields)}}


# ----------------------------------------------------------------- hojas base
def setup_base(ss):
    reg = get_or_create(ss, REGISTRO, 5000, 7)
    reg.update(range_name="A1:G1", values=[HEADERS])
    cat = get_or_create(ss, CATEGORIAS, 500, 2)
    if not cat.get_all_values()[1:]:
        cat.update(range_name="A1", values=[["Palabra clave", "Categoría"]] + [list(r) for r in DEFAULT_RULES])
    meta = get_or_create(ss, META, 10, 3)
    existing = meta.acell("B1").value
    meta.update(range_name="A1:B2", values=[["next_id", existing or 1], ["updates", meta.acell("B2").value or ""]],
                value_input_option="RAW")
    res = get_or_create(ss, RESUMEN, 30, 4)
    ing = 'SUMIFS(Registro!$D:$D,Registro!$B:$B,">="&DATE($B$1,$B$2,1),Registro!$B:$B,"<"&EDATE(DATE($B$1,$B$2,1),1),Registro!$D:$D,"{}")'
    res.update(range_name="A1:B6", value_input_option="USER_ENTERED", values=[
        ["Año", res.acell("B1").value or 2026], ["Mes", res.acell("B2").value or 1], [],
        ["Ingresos", "=" + ing.format(">0")], ["Gastos", "=" + ing.format("<0")], ["Balance", "=B4+B5"]])
    return reg, cat, meta, res


def format_base(ss, reg, cat, meta, res):
    ss.batch_update({"requests": [
        {"updateSpreadsheetProperties": {"properties": {"timeZone": "Europe/Madrid"}, "fields": "timeZone"}},
        {"updateSheetProperties": {"properties": {"sheetId": reg.id, "gridProperties": {"frozenRowCount": 1}},
                                   "fields": "gridProperties.frozenRowCount"}},
        fmt(reg.id, 0, 1, 0, 7, bold=True, bg=BLUE, fg=WHITE),
        fmt(reg.id, 1, 5000, 1, 2, number={"type": "DATE", "pattern": "dd/mm/yyyy"}),
        fmt(reg.id, 1, 5000, 3, 4, number=EUR),
        fmt(reg.id, 1, 5000, 6, 7, number={"type": "DATE_TIME", "pattern": "dd/mm/yyyy hh:mm"}),
        fmt(cat.id, 0, 1, 0, 2, bold=True, bg=BLUE, fg=WHITE),
        fmt(res.id, 3, 6, 1, 2, number=EUR, bold=True),
        fmt(res.id, 0, 3, 0, 1, bold=True),
        list_rule(res.id, 0, 1, 1, 2, values=range(2024, 2036)),
        list_rule(res.id, 1, 2, 1, 2, values=range(1, 13)),
        {"updateSheetProperties": {"properties": {"sheetId": meta.id, "hidden": True}, "fields": "hidden"}},
        {"addProtectedRange": {"protectedRange": {"range": rng(meta.id, 0, 10, 0, 3),
                                                  "description": "Gestionado por el bot", "warningOnly": True}}},
    ]})


# ------------------------------------------------------------------ dashboard
def build_dashboard(ss):
    try:
        ss.del_worksheet(ss.worksheet(DASHBOARD))
    except Exception:  # noqa: BLE001
        pass
    ws = ss.add_worksheet(DASHBOARD, 400, 40, index=0)
    sid = ws.id
    D, B, E = "Registro!$D:$D", "Registro!$B:$B", "Registro!$E:$E"
    crit = 'IF($C$4="Todas","*",$C$4)'

    def sumifs(sign, start, end):
        return f'SUMIFS({D},{B},">="&{start},{B},"<"&{end},{D},"{sign}",{E},{crit})'

    def qdate(cell):  # literal de fecha QUERY, independiente del locale (sin TEXT())
        return f'"date \'"&YEAR({cell})&"-"&RIGHT("0"&MONTH({cell}),2)&"-"&RIGHT("0"&DAY({cell}),2)&"\'"'

    catq = f'IF($C$4="Todas",""," and E=\'"&$C$4&"\'")'  # sin «&» inicial: se une con '&' donde se usa
    meses = '{' + ",".join(f'"{m}"' for m in MESES) + '}'

    cells: dict[str, object] = {
        "B2": "Año", "C2": 2026,
        "B3": "Mes", "C3": "Todo el año",
        "B4": "Categoría", "C4": "Todas",
        "E2": "Selecciona Año, Mes y Categoría: todo el dashboard se recalcula.",
        # --- ayudantes (columnas V:AF, zona técnica) ---
        "V1": "Ayudantes (no editar)",
        "V2": "mes nº", "W2": f'=IFERROR(MATCH($C$3,{meses},0),0)',
        "V3": "inicio", "W3": "=DATE($C$2,IF($W$2=0,1,$W$2),1)",
        "V4": "fin", "W4": "=IF($W$2=0,DATE($C$2+1,1,1),EDATE($W$3,1))",
        "V5": "inicio ant.", "W5": "=EDATE($W$3,IF($W$2=0,-12,-1))",
        "V6": "días", "W6": "=MAX(1,MIN($W$4,TODAY()+1)-$W$3)",
        "V7": "categorías", "W7": '={"Todas";"Otros";"Ingresos varios";SORT(UNIQUE(FILTER(\'Categorías\'!$B$2:$B,\'Categorías\'!$B$2:$B<>"")))}',
        # --- KPIs ---
        "B6": "Ingresos", "C6": "Gastos", "D6": "Balance", "E6": "Tasa de ahorro", "F6": "Gasto medio diario", "G6": "Gasto vs. periodo ant.",
        "B7": "=" + sumifs(">0", "$W$3", "$W$4"),
        "C7": "=" + sumifs("<0", "$W$3", "$W$4"),
        "D7": "=B7+C7",
        "E7": '=IF(B7=0,"–",D7/B7)',
        "F7": "=-C7/$W$6",
        "G7": '=IFERROR((C7-' + sumifs("<0", "$W$5", "$W$3") + ')/ABS(' + sumifs("<0", "$W$5", "$W$3") + '),"–")',
        # --- tabla gasto por categoría con sparkline ---
        "B10": "Gasto por categoría", "B11": "Categoría", "C11": "Gasto", "D11": "% del total", "E11": "", "F11": "Evolución 12 meses",
        # --- Top 10 ---
        "B26": "Top 10 gastos del periodo",
        "B27": '=IFERROR(QUERY(Registro!$A:$G,"select A,B,C,D,E where D<0 and B>="&' + qdate("$W$3") +
               '&" and B<"&' + qdate("$W$4") + '&' + catq + '&" order by D asc limit 10 label A \'ID\',B \'Fecha\',C \'Concepto\',D \'Importe\',E \'Categoría\'",0),"Sin datos")',
        # --- bloque A: gasto por categoría (alimenta donut) ---
        "Y1": "Categoría", "Z1": "Gasto",
        "Y2": '=IFERROR(SORT(QUERY(Registro!$A:$G,"select E,sum(D)*-1 where D<0 and B>="&' + qdate("$W$3") +
              '&" and B<"&' + qdate("$W$4") + '&' + catq + '&" group by E label sum(D)*-1 \'\'",0),2,FALSE),{"Sin datos",0})',
        # --- bloque B: meses del año ---
        "AB1": "Mes", "AC1": "Ingresos", "AD1": "Gastos", "AE1": "Balance",
        # --- bloque C: saldo acumulado diario ---
        "AG1": "Fecha", "AH1": "Saldo acumulado",
    }
    for i in range(12):
        r = i + 2
        s, e = f"DATE($C$2,{i + 1},1)", f"EDATE(DATE($C$2,{i + 1},1),1)"
        cells[f"AB{r}"] = MESES[i][:3]
        cells[f"AC{r}"] = "=" + sumifs(">0", s, e)
        cells[f"AD{r}"] = "=-" + sumifs("<0", s, e)
        cells[f"AE{r}"] = f"=AC{r}-AD{r}"
    for n in range(366):
        r = n + 2
        cells[f"AG{r}"] = f'=IF($W$3+{n}<$W$4,$W$3+{n},NA())'
        cells[f"AH{r}"] = f'=IF(ISNA(AG{r}),NA(),SUMIFS({D},{B},">="&$W$3,{B},"<="&AG{r},{E},{crit}))'
    for i in range(10):  # tabla categorías + sparkline (filas 12..21)
        r, k = 12 + i, i + 2
        k = i + 1  # el bloque A ya no lleva cabecera dentro del QUERY (empieza en Y2)
        cells[f"B{r}"] = f'=IFERROR(INDEX($Y$2:$Z$40,{k},1),"")'
        cells[f"C{r}"] = f'=IF(B{r}="","",INDEX($Y$2:$Z$40,{k},2))'
        cells[f"D{r}"] = f'=IF(B{r}="","",IFERROR(C{r}/-$C$7,0))'
        cells[f"E{r}"] = f'=IF(B{r}="","",SPARKLINE(D{r},{{"charttype","bar";"max",1;"color1","#1a57a0"}}))'
        cells[f"F{r}"] = (f'=IF(B{r}="","",SPARKLINE(ARRAYFORMULA(-SUMIFS({D},{E},B{r},'
                          f'{B},">="&DATE($C$2,SEQUENCE(1,12),1),{B},"<"&DATE($C$2,SEQUENCE(1,12)+1,1))),'
                          f'{{"charttype","column";"color","#1a57a0"}}))')

    data = []
    for addr, val in cells.items():
        data.append({"range": f"{DASHBOARD}!{addr}", "values": [[val]]})
    ss.values_batch_update({"valueInputOption": "USER_ENTERED", "data": data})

    anchors = {  # (fila, columna) 0-based
        "donut": (28 + 12, 1), "bars": (28 + 12, 5), "line": (28 + 30, 1)}

    def chart(title, spec, row, col, w=520, h=300):
        return {"addChart": {"chart": {"spec": {"title": title, "hiddenDimensionStrategy": "SHOW_ALL", **spec}, "position": {"overlayPosition": {
            "anchorCell": {"sheetId": sid, "rowIndex": row, "columnIndex": col},
            "widthPixels": w, "heightPixels": h}}}}}

    def src(c0, c1, r0=0, r1=13):
        return {"sourceRange": {"sources": [rng(sid, r0, r1, c0, c1)]}}

    donut = {"pieChart": {"legendPosition": "RIGHT_LEGEND", "pieHole": 0.5,
                          "domain": src(24, 25, 1, 13), "series": src(25, 26, 1, 13)}}
    combo = {"basicChart": {"chartType": "COMBO", "legendPosition": "BOTTOM_LEGEND", "headerCount": 1,
                            "axis": [{"position": "BOTTOM_AXIS"}, {"position": "LEFT_AXIS"}],
                            "domains": [{"domain": src(27, 28)}],
                            "series": [{"series": src(28, 29), "type": "COLUMN", "color": {"red": .18, "green": .49, "blue": .2}},
                                       {"series": src(29, 30), "type": "COLUMN", "color": {"red": .78, "green": .16, "blue": .16}},
                                       {"series": src(30, 31), "type": "LINE", "color": {"red": .08, "green": .4, "blue": .75}}]}}
    line = {"basicChart": {"chartType": "LINE", "legendPosition": "NO_LEGEND", "headerCount": 1,
                           "axis": [{"position": "BOTTOM_AXIS"}, {"position": "LEFT_AXIS"}],
                           "domains": [{"domain": src(32, 33, 0, 367)}],
                           "series": [{"series": src(33, 34, 0, 367), "color": {"red": .08, "green": .4, "blue": .75}}]}}

    ss.batch_update({"requests": [
        list_rule(sid, 1, 2, 2, 3, values=range(2024, 2036)),
        list_rule(sid, 2, 3, 2, 3, values=["Todo el año"] + MESES),
        list_rule(sid, 3, 4, 2, 3, source="=Dashboard!$W$7:$W$60"),
        fmt(sid, 0, 200, 0, 8, bg=WHITE),
        fmt(sid, 1, 4, 1, 2, bold=True, bg=GREY),
        fmt(sid, 1, 4, 2, 3, bold=True, bg={"red": 1, "green": .96, "blue": .8}),
        fmt(sid, 1, 2, 4, 5, fg={"red": .4, "green": .4, "blue": .4}),
        fmt(sid, 5, 6, 1, 7, bold=True, bg=BLUE, fg=WHITE, align="CENTER"),
        fmt(sid, 6, 7, 1, 7, size=16, bold=True, align="CENTER", bg=GREY),
        fmt(sid, 6, 7, 1, 4, number=EUR), fmt(sid, 6, 7, 5, 6, number=EUR),
        fmt(sid, 6, 7, 4, 5, number={"type": "PERCENT", "pattern": "0.0%"}),
        fmt(sid, 6, 7, 6, 7, number={"type": "NUMBER", "pattern": "[Red]▲ 0.0%;[Color10]▼ 0.0%;0.0%"}),
        fmt(sid, 9, 10, 1, 2, bold=True, size=12), fmt(sid, 25, 26, 1, 2, bold=True, size=12),
        fmt(sid, 10, 11, 1, 7, bold=True, bg=BLUE, fg=WHITE),
        fmt(sid, 11, 21, 2, 3, number=EUR), fmt(sid, 11, 21, 3, 4, number={"type": "PERCENT", "pattern": "0%"}),
        fmt(sid, 27, 38, 4, 5, number=EUR),  # Top 10: columna E = Importe
        fmt(sid, 27, 38, 2, 3, number={"type": "DATE", "pattern": "dd/mm/yyyy"}),  # columna C = Fecha
        fmt(sid, 0, 40, 21, 34, fg={"red": .55, "green": .55, "blue": .55}),
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 7},
                                       "properties": {"pixelSize": 150}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 21, "endIndex": 34},
                                       "properties": {"hiddenByUser": True}, "fields": "hiddenByUser"}},
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}},
                                   "fields": "gridProperties.hideGridlines"}},
        chart("Gastos por categoría", donut, *anchors["donut"]),
        chart("Ingresos vs gastos por mes", combo, *anchors["bars"], w=620),
        chart("Saldo acumulado del periodo", line, *anchors["line"], w=1140),
    ]})
    return ws


def set_locale(ss, locale):
    ss.batch_update({"requests": [{"updateSpreadsheetProperties": {
        "properties": {"locale": locale}, "fields": "locale"}}]})


def drop_default_sheet(ss):
    """Elimina la hoja por defecto vacía («Hoja 1» / «Sheet1») si no contiene datos."""
    for ws in ss.worksheets():
        if ws.title in ("Hoja 1", "Sheet1") and not any(any(r) for r in ws.get_all_values()):
            ss.del_worksheet(ws)


def main():
    ss = open_spreadsheet(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"], os.environ["SPREADSHEET_ID"])
    # Las fórmulas escritas con USER_ENTERED se interpretan según el locale de la hoja (en es_ES
    # exigirían «;»). Se escriben con en_US (comas) y se pasa a es_ES al final: Sheets las
    # guarda de forma neutra y las muestra con el formato español.
    set_locale(ss, "en_US")
    try:
        reg, cat, meta, res = setup_base(ss)
        format_base(ss, reg, cat, meta, res)
        build_dashboard(ss)
    finally:
        set_locale(ss, "es_ES")
    drop_default_sheet(ss)
    print("Hoja lista:", ss.url)


if __name__ == "__main__":
    main()
