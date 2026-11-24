"""Genera docs/index.html (página de presentación) a partir de spam_teoria_decision.ipynb.

Uso:  python build_html.py
El notebook sigue siendo la fuente: aquí solo se cambia cómo se ve.
"""
import html
import json
import re
from pathlib import Path

import mistune
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

AQUI = Path(__file__).parent
NB = AQUI / "spam_teoria_decision.ipynb"
SALIDA = AQUI / "docs" / "index.html"

md = mistune.create_markdown(escape=False, plugins=["table", "strikethrough"])
FORMATO_CODIGO = HtmlFormatter(nowrap=True, style="default")


# ---------------------------------------------------------------- markdown + matemáticas
def render_md(texto):
    """Markdown -> HTML protegiendo las fórmulas $...$ y $$...$$ para que MathJax las vea intactas."""
    mates = []

    def guardar(m):
        mates.append(m.group(0))
        return f"MATHPH{len(mates) - 1}X"

    texto = re.sub(r"\$\$.+?\$\$", guardar, texto, flags=re.S)
    texto = re.sub(r"\$[^$\n]+?\$", guardar, texto)
    salida = md(texto)
    for i, formula in enumerate(mates):
        if formula.startswith("$$"):
            partes = [x.strip() for x in formula[2:-2].split(r"\qquad\qquad")]
            cajas = "".join(f'<div class="eq">{html.escape("$$" + x + "$$", quote=False)}</div>' for x in partes)
            salida = salida.replace(f"<p>MATHPH{i}X</p>", f'<div class="eqs">{cajas}</div>')
        salida = salida.replace(f"MATHPH{i}X", html.escape(formula, quote=False))
    return salida


def decorar(salida):
    """Retoques de HTML para que las tablas del notebook tengan significado visual."""
    salida = salida.replace("<td>Falso positivo (FP):", '<td><span class="tag tag-fp">Falso positivo (FP)</span>')
    salida = salida.replace("<td>Falso negativo (FN):", '<td><span class="tag tag-fn">Falso negativo (FN)</span>')
    salida = re.sub(r'<span class="tag tag-fp">Falso positivo \(FP\)</span>(.*?)</td>',
                    r'<span class="tag tag-fp">Falso positivo (FP)</span><div class="sub">\1</div></td>', salida, count=1, flags=re.S)
    salida = re.sub(r'<span class="tag tag-fn">Falso negativo \(FN\)</span>(.*?)</td>',
                    r'<span class="tag tag-fn">Falso negativo (FN)</span><div class="sub">\1</div></td>', salida, count=1, flags=re.S)
    # tabla comparativa de filtros: la última fila es la que gana
    salida = re.sub(r"(<table>\s*<thead>.*?Acierto.*?</thead>\s*<tbody>.*?)(<tr>(?:(?!<tr>).)*?</tr>)(\s*</tbody>)",
                    lambda m: m.group(1) + m.group(2).replace("<tr>", '<tr class="gana">', 1) + m.group(3), salida, count=1, flags=re.S)
    salida = re.sub(r"<table>", '<div class="tabla"><table>', salida)
    salida = salida.replace("</table>", "</table></div>")
    return salida


def partir_pasos(salida):
    """Agrupa cada <h3> con su contenido en una tarjeta 'paso'."""
    trozos = re.split(r"(?=<h3>)", salida)
    if len(trozos) < 2:
        return salida
    cabeza, pasos = trozos[0], trozos[1:]
    return cabeza + "".join(f'<div class="paso">{p}</div>' for p in pasos)


# ---------------------------------------------------------------- salidas de código
def salida_celda(o):
    if o["output_type"] == "stream":
        return f'<pre class="stream">{html.escape("".join(o["text"]).strip())}</pre>'
    datos = o.get("data", {})
    if "image/png" in datos:
        return f'<div class="figura"><img alt="Gráficas de comprobación" src="data:image/png;base64,{datos["image/png"].strip()}"></div>'
    if "text/html" in datos:
        tabla = "".join(datos["text/html"])
        tabla = re.sub(r"<style.*?</style>", "", tabla, flags=re.S)
        tabla = re.sub(r'\s(id|class)="[^"]*"', "", tabla)
        return f'<div class="tabla resultado">{tabla}</div>'
    return ""


def celda_codigo(c):
    codigo = highlight("".join(c["source"]), PythonLexer(), FORMATO_CODIGO)
    partes = [f'<details class="codigo"><summary>Ver código</summary><pre class="hl">{codigo}</pre></details>']
    partes += [salida_celda(o) for o in c.get("outputs", [])]
    return "\n".join(partes)


# ---------------------------------------------------------------- KPIs a partir de las salidas
def kpis(nb):
    """Saca coste/FP/ahorro del propio notebook para el panel de cifras. Si algo no cuadra, no hay panel."""
    try:
        salida = next(c["outputs"] for c in nb["cells"] if any(o.get("data", {}).get("text/html") for o in c.get("outputs", [])))
        tabla = next(o for o in salida if o["output_type"] == "display_data")["data"]["text/html"]
        tabla = "".join(tabla)
        filas = re.findall(r"<tr>\s*<th[^>]*>(.*?)</th>(.*?)</tr>", tabla, flags=re.S)
        valores = [[html.unescape(re.sub(r"<[^>]+>", "", v)).strip() for v in re.findall(r"<td[^>]*>(.*?)</td>", r[1], flags=re.S)] for r in filas]
        valores = [v for v in valores if v]  # la fila de cabecera no tiene <td>
        fp0, fn0, _, c0 = valores[0]
        fp1, fn1, _, c1 = valores[1]
        texto = "".join(next(o for o in salida if o["output_type"] == "stream")["text"])
        pct, lo, hi = re.search(r"\((\d+)% menos coste\).*?\[(-?\d+), (-?\d+)\]", texto).groups()
    except Exception:
        return ""
    return f"""
<div class="kpis">
  <div class="kpi"><span class="k-lab">Coste total en prueba</span><span class="k-val">{c0} <i>→</i> {c1}</span><span class="k-sub">umbral 0,5 → umbral t*</span></div>
  <div class="kpi kpi-hi"><span class="k-lab">Ahorro</span><span class="k-val">−{pct} %</span><span class="k-sub">bootstrap 95 %: [{lo}, {hi}]</span></div>
  <div class="kpi"><span class="k-lab">Legítimos perdidos (FP)</span><span class="k-val">{fp0} <i>→</i> {fp1}</span><span class="k-sub">los errores caros</span></div>
  <div class="kpi"><span class="k-lab">Spam que se cuela (FN)</span><span class="k-val">{fn0} <i>→</i> {fn1}</span><span class="k-sub">los errores baratos</span></div>
</div>"""


# ---------------------------------------------------------------- página
def construir():
    nb = json.loads(NB.read_text(encoding="utf-8"))
    celdas = nb["cells"]

    hero = render_md("".join(celdas[0]["source"]))
    secciones = []  # (id, titulo, [html...])
    anterior = ""
    for c in celdas[1:]:
        fuente = "".join(c["source"])
        if c["cell_type"] == "markdown":
            if not fuente.strip() or (fuente.strip() in anterior and len(fuente.strip()) > 40):
                continue  # celda vacía o copia literal de lo ya escrito
            anterior = fuente
            if fuente.startswith("## "):
                titulo = fuente.splitlines()[0][3:].strip()
                secciones.append((f"s{len(secciones) + 1}", titulo, []))
                fuente = "\n".join(fuente.splitlines()[1:])
            cuerpo = decorar(render_md(fuente))
            if secciones and secciones[-1][1].startswith("2."):
                cuerpo = partir_pasos(cuerpo)
            secciones[-1][2].append(cuerpo)
        else:
            secciones[-1][2].append(celda_codigo(c))
            if secciones[-1][1].startswith("3."):
                pass

    panel = kpis(nb)
    nav = "".join(f'<a href="#{i}">{html.escape(re.sub(r"^\d+\.\s*", "", t))}</a>' for i, t, _ in secciones)
    cuerpo = []
    for i, t, partes in secciones:
        numero, _, texto = t.partition(". ")
        extra = panel if t.startswith("3.") else ""
        contenido = "\n".join(partes)
        contenido = re.sub(r"<li><strong>([^<]*?):</strong>", r"<li><strong>\1</strong>", contenido)  # etiquetas sin dos puntos
        if extra:  # el panel de cifras va justo después del título de la demostración
            contenido = extra + contenido
        cuerpo.append(f'<section id="{i}" class="card"><header><span class="num">{html.escape(numero)}</span><h2>{html.escape(texto)}</h2></header>{contenido}</section>')

    pagina = PLANTILLA.replace("{{HERO}}", hero).replace("{{NAV}}", nav).replace("{{CUERPO}}", "\n".join(cuerpo))
    pagina = pagina.replace("{{PYGMENTS}}", HtmlFormatter(style="default").get_style_defs(".hl"))
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(pagina, encoding="utf-8")
    (SALIDA.parent / ".nojekyll").touch()
    print(f"Escrito {SALIDA} ({SALIDA.stat().st_size // 1024} KB)")


PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spam y teoría de la decisión</title>
<meta name="description" content="Filtros de spam: decidir bien cuando los errores no cuestan lo mismo.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<script>
window.MathJax = { tex: { inlineMath: [['$', '$']], displayMath: [['$$', '$$']] }, chtml: { scale: 1.08 } };
</script>
<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"></script>
<style>
:root{--bg:#fafaf8;--ink:#15171c;--txt:#2b2e35;--mut:#6c7079;--line:#e3e3de;--soft:#f2f2ee}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--txt);font:18px/1.7 Inter,system-ui,-apple-system,Segoe UI,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--ink)}
.wrap{max-width:860px;margin:0 auto;padding:0 24px}

/* navegación */
.nav{position:sticky;top:0;z-index:20;background:#fafaf8ee;backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.nav .wrap{display:flex;gap:26px;align-items:center;height:52px;overflow-x:auto;max-width:1000px}
.nav b{font-weight:600;font-size:14px;color:var(--ink);margin-right:auto;white-space:nowrap}
.nav a{color:var(--mut);text-decoration:none;font-size:14px;white-space:nowrap;padding:16px 0 14px;border-bottom:2px solid transparent;transition:color .15s}
.nav a:hover{color:var(--ink)}
.nav a.on{color:var(--ink);border-bottom-color:var(--ink)}
.progreso{position:absolute;left:0;bottom:-1px;height:1px;background:var(--ink);width:0}

/* cabecera */
.hero{padding:104px 0 56px}
.hero h1{font-size:clamp(34px,5vw,54px);line-height:1.12;letter-spacing:-.03em;margin:0 0 28px;font-weight:700;color:var(--ink)}
.hero p{margin:0 0 40px;font-size:15px;color:var(--mut)}
.hero p em{font-style:normal;color:var(--ink)}
.hero blockquote{margin:0;padding:2px 0 2px 24px;border-left:3px solid var(--ink);font-size:21px;line-height:1.55;color:var(--ink);font-weight:500}
.hero blockquote p{margin:0;font-size:inherit;color:inherit}

/* secciones */
.card{border-top:1px solid var(--line);padding:64px 0 24px;margin:0}
.card>header{margin-bottom:26px}
.num{display:block;font:500 13px 'JetBrains Mono',monospace;letter-spacing:.08em;color:var(--mut);margin-bottom:8px}
.num::before{content:"0"}
.card h2{margin:0;font-size:34px;line-height:1.2;letter-spacing:-.025em;font-weight:700;color:var(--ink)}
.card p{margin:0 0 16px}
.card ul{padding:0;list-style:none;margin:16px 0}
.card li{position:relative;padding-left:24px;margin:10px 0}
.card li::before{content:"–";position:absolute;left:2px;color:var(--mut)}
strong{color:var(--ink);font-weight:600}
code{font:14px 'JetBrains Mono',monospace;background:var(--soft);padding:1px 6px;border-radius:4px;color:var(--ink)}
.card h3{font-size:21px;margin:34px 0 12px;color:var(--ink);font-weight:600;letter-spacing:-.01em}

/* pasos */
.paso{border-left:2px solid var(--line);padding:2px 0 2px 28px;margin:36px 0}
.paso h3{margin:0 0 14px}

/* ecuaciones */
.eqs{display:flex;flex-direction:column}
.eq{background:var(--soft);border-radius:6px;padding:14px 18px;margin:10px 0;overflow-x:auto;text-align:center;font-size:17px;color:var(--ink)}

/* tablas */
.tabla{margin:28px 0;overflow-x:auto;border-top:2px solid var(--ink);border-bottom:1px solid var(--ink)}
table{border-collapse:collapse;width:100%;font-size:16px}
th{text-align:left;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);padding:14px 16px 10px;border-bottom:1px solid var(--line)}
td{padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--txt)}
tbody tr:last-child td{border-bottom:0}
.tag{display:block;font-weight:600;color:var(--ink);font-size:16px}
.sub{color:var(--mut);font-size:15px}
tr.gana td{font-weight:600;color:var(--ink);background:var(--soft)}
.tabla.resultado th{text-transform:none;font-size:14px;letter-spacing:0}
.tabla.resultado tbody th{font-size:16px;color:var(--ink);font-weight:600;text-transform:none;letter-spacing:0;border-bottom:1px solid var(--line);vertical-align:middle}
.tabla.resultado td{font-variant-numeric:tabular-nums;font-size:19px;vertical-align:middle}
.tabla.resultado tbody tr:last-child th,.tabla.resultado tbody tr:last-child td{background:var(--soft);font-weight:700;color:var(--ink);border-bottom:0}

/* cifras clave */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:0;margin:8px 0 40px;border-top:2px solid var(--ink)}
.kpi{padding:18px 18px 4px 0;display:flex;flex-direction:column;gap:2px}
.kpi+.kpi{padding-left:18px;border-left:1px solid var(--line)}
.k-lab{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);font-weight:600}
.k-val{font-size:34px;font-weight:700;letter-spacing:-.03em;white-space:nowrap;color:var(--ink);line-height:1.2}
.k-val i{font-style:normal;color:var(--mut);font-weight:400}
.k-sub{font-size:13px;color:var(--mut)}

/* código y resultados */
details.codigo{margin:20px 0 8px}
details.codigo summary{cursor:pointer;display:inline-block;color:var(--mut);font-size:14px;list-style:none;border-bottom:1px solid var(--line);padding-bottom:1px}
details.codigo summary::-webkit-details-marker{display:none}
details.codigo summary:hover{color:var(--ink);border-bottom-color:var(--ink)}
pre{margin:14px 0 0;border-radius:6px;overflow-x:auto}
pre.hl{background:var(--soft);padding:18px 22px;font:13.5px/1.6 'JetBrains Mono',monospace;color:var(--ink)}
pre.stream{background:transparent;border-left:2px solid var(--ink);padding:4px 0 4px 18px;font:14.5px/1.65 'JetBrains Mono',monospace;color:var(--ink);margin:16px 0;border-radius:0}
.figura{border:1px solid var(--line);border-radius:6px;padding:12px;margin:24px 0;background:#fff}
.figura img{width:100%;display:block}
{{PYGMENTS}}

/* conclusión */
#s4 ul{display:grid;grid-template-columns:repeat(3,1fr);gap:28px;margin:10px 0 24px}
#s4 li{padding:16px 0 0;border-top:2px solid var(--ink);margin:0;font-size:16px;line-height:1.6}
#s4 li::before{display:none}
#s4 li strong:first-child{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin-bottom:8px}

footer{padding:40px 0 70px;text-align:left;color:var(--mut);font-size:14px;border-top:1px solid var(--line);margin-top:40px}

@media (max-width:860px){
  body{font-size:17px}.card h2{font-size:28px}.hero{padding-top:56px}.kpis{grid-template-columns:1fr 1fr}
  .kpi:nth-child(3){padding-left:0;border-left:0}.kpi:nth-child(n+3){border-top:1px solid var(--line);margin-top:10px}
  #s4 ul{grid-template-columns:1fr}.nav .wrap{gap:18px}
}
@media print{.nav{display:none}}
</style>
</head>
<body>
<nav class="nav"><div class="wrap"><b>Spam &amp; decisión</b>{{NAV}}</div><div class="progreso" id="prog"></div></nav>
<main class="wrap">
  <div class="hero">{{HERO}}</div>
  {{CUERPO}}
</main>
<footer>Aprendizaje Automático · datos: Spambase (UCI) · código y notebook en el repositorio</footer>
<script>
const enlaces=[...document.querySelectorAll('.nav a')],secs=enlaces.map(a=>document.querySelector(a.getAttribute('href')));
const prog=document.getElementById('prog');
function alScroll(){
  const h=document.documentElement;prog.style.width=(100*h.scrollTop/(h.scrollHeight-h.clientHeight))+'%';
  let activa=0;secs.forEach((s,i)=>{if(s.getBoundingClientRect().top<140)activa=i});
  enlaces.forEach((a,i)=>a.classList.toggle('on',i===activa));
}
addEventListener('scroll',alScroll,{passive:true});alScroll();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    construir()
