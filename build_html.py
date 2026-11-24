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
FORMATO_CODIGO = HtmlFormatter(nowrap=True, style="monokai")


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
    salida = salida.replace("<td>Falso positivo (FP):", '<td><span class="tag tag-fp">Falso positivo · FP</span>')
    salida = salida.replace("<td>Falso negativo (FN):", '<td><span class="tag tag-fn">Falso negativo · FN</span>')
    salida = re.sub(r'<span class="tag tag-fp">Falso positivo · FP</span>(.*?)</td>',
                    r'<span class="tag tag-fp">Falso positivo · FP</span><div class="sub">\1</div></td>', salida, count=1, flags=re.S)
    salida = re.sub(r'<span class="tag tag-fn">Falso negativo · FN</span>(.*?)</td>',
                    r'<span class="tag tag-fn">Falso negativo · FN</span><div class="sub">\1</div></td>', salida, count=1, flags=re.S)
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
        if extra:  # el panel de cifras va justo después del título de la demostración
            contenido = extra + contenido
        cuerpo.append(f'<section id="{i}" class="card"><header><span class="num">{html.escape(numero)}</span><h2>{html.escape(texto)}</h2></header>{contenido}</section>')

    pagina = PLANTILLA.replace("{{HERO}}", hero).replace("{{NAV}}", nav).replace("{{CUERPO}}", "\n".join(cuerpo))
    pagina = pagina.replace("{{PYGMENTS}}", HtmlFormatter(style="monokai").get_style_defs(".hl"))
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
:root{
  --bg:#0b1020; --bg2:#121a33; --card:#151e3a; --card2:#1b2647; --line:#2a3766;
  --txt:#e8ecf8; --mut:#9aa6c8; --acc:#5b9dff; --acc2:#7c5cff;
  --fp:#ff6b6b; --fn:#4dd4ac; --gold:#ffd166; --ok:#4dd4ac;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:70px}
body{margin:0;background:radial-gradient(1200px 600px at 80% -10%,#1b2a6b55,transparent),var(--bg);color:var(--txt);
  font:17px/1.65 Inter,system-ui,-apple-system,Segoe UI,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--acc)}
.wrap{max-width:1020px;margin:0 auto;padding:0 20px}

/* barra de navegación */
.nav{position:sticky;top:0;z-index:20;background:#0b1020d9;backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.nav .wrap{display:flex;gap:6px;align-items:center;height:52px;overflow-x:auto}
.nav b{font-weight:800;margin-right:12px;white-space:nowrap;background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;color:transparent}
.nav a{color:var(--mut);text-decoration:none;font-size:14px;font-weight:500;padding:6px 12px;border-radius:99px;white-space:nowrap;transition:.2s}
.nav a:hover,.nav a.on{color:#fff;background:var(--card2)}
.progreso{position:absolute;left:0;bottom:-1px;height:2px;background:linear-gradient(90deg,var(--acc),var(--acc2));width:0}

/* cabecera */
.hero{padding:72px 0 40px}
.hero h1{font-size:clamp(34px,5.4vw,58px);line-height:1.08;letter-spacing:-.025em;margin:0 0 22px;font-weight:800;
  background:linear-gradient(100deg,#fff 20%,#9cc2ff 60%,#b9a8ff);-webkit-background-clip:text;color:transparent}
.hero p{color:var(--mut);margin:0 0 26px;font-size:16px}
.hero p em{color:var(--txt);font-style:normal;font-weight:500}
.hero blockquote{margin:0;padding:22px 26px;border-radius:18px;background:linear-gradient(135deg,#1c2b66,#2a1f66);
  border:1px solid #3d4d96;font-size:19px;line-height:1.55;color:#f1f4ff;box-shadow:0 20px 60px -20px #5b9dff55}
.hero blockquote p{margin:0;color:inherit;font-size:inherit}

/* tarjetas de sección */
.card{background:linear-gradient(180deg,var(--card),var(--bg2));border:1px solid var(--line);border-radius:24px;padding:34px 38px;margin:0 0 28px;
  box-shadow:0 30px 80px -40px #000}
.card>header{display:flex;align-items:center;gap:16px;margin-bottom:18px}
.card h2{margin:0;font-size:30px;letter-spacing:-.02em;font-weight:800}
.num{flex:none;width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-weight:800;font-size:20px;
  background:linear-gradient(135deg,var(--acc),var(--acc2));color:#fff;box-shadow:0 8px 24px -8px var(--acc)}
.card p{margin:0 0 14px}
.card ul{padding-left:0;list-style:none;margin:14px 0}
.card li{position:relative;padding-left:26px;margin:9px 0}
.card li::before{content:"";position:absolute;left:4px;top:.68em;width:9px;height:9px;border-radius:3px;background:linear-gradient(135deg,var(--acc),var(--acc2))}
strong{color:#fff;font-weight:700;background:linear-gradient(transparent 62%,#5b9dff40 62%);padding:0 2px}
code{font:14px 'JetBrains Mono',monospace;background:#0b1230;border:1px solid var(--line);padding:1px 7px;border-radius:7px;color:#cfe0ff}

/* pasos (sección 2) */
.paso{background:#0f1730;border:1px solid var(--line);border-radius:18px;padding:22px 26px;margin:18px 0}
.paso h3{margin:0 0 12px;font-size:21px;font-weight:700;color:#fff}
.paso:nth-of-type(1) h3{color:#8fc0ff}.paso:nth-of-type(2) h3{color:#ffd98a}
.paso{border-left:4px solid var(--acc)}
.paso:nth-of-type(2){border-left-color:var(--gold)}
.card h3{font-size:21px;margin:26px 0 12px}

/* ecuaciones */
.eqs{display:flex;flex-direction:column;gap:0}.eqs .eq{margin:8px 0}
.eq{background:#0b1230;border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin:14px 0;overflow-x:auto;text-align:center;font-size:17px}

/* tablas */
.tabla{margin:20px 0;border-radius:16px;overflow:hidden;border:1px solid var(--line);overflow-x:auto;background:#0e1631}
table{border-collapse:collapse;width:100%;font-size:16px}
th{background:#1b2750;color:#bcd0ff;text-align:left;font-weight:600;padding:13px 18px;font-size:13px;text-transform:uppercase;letter-spacing:.06em}
td{padding:14px 18px;border-top:1px solid var(--line);vertical-align:middle}
tbody tr:hover td{background:#17224a}
td:last-child,th:last-child{text-align:left}
.tag{display:inline-block;padding:3px 12px;border-radius:99px;font-weight:700;font-size:14px;margin-bottom:4px}
.tag-fp{background:#ff6b6b26;color:var(--fp);border:1px solid #ff6b6b66}
.tag-fn{background:#4dd4ac26;color:var(--fn);border:1px solid #4dd4ac66}
.sub{color:var(--mut);font-size:15px}
tr.gana td{background:#4dd4ac14;color:#d8fff3;font-weight:600}
tr.gana td:first-child{box-shadow:inset 4px 0 var(--ok)}
.tabla.resultado th{text-transform:none;font-size:14px;letter-spacing:0}
.tabla.resultado tbody tr:last-child td{background:#4dd4ac14;color:#d8fff3;font-weight:600}
.tabla.resultado tbody tr:last-child th{box-shadow:inset 4px 0 var(--ok);color:#d8fff3}
.tabla.resultado tbody th{background:#131d40;color:#fff;text-transform:none;font-size:15px;letter-spacing:0;border-top:1px solid var(--line)}
.tabla.resultado td{font-variant-numeric:tabular-nums;font-size:18px}

/* cifras clave */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:6px 0 26px}
.kpi{background:#0e1631;border:1px solid var(--line);border-radius:18px;padding:18px 20px;display:flex;flex-direction:column;gap:2px}
.kpi-hi{background:linear-gradient(135deg,#17744f,#1a5f78);border-color:#3fe0a8}
.k-lab{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);font-weight:600}
.kpi-hi .k-lab,.kpi-hi .k-sub{color:#cffbe9}
.k-val{font-size:30px;font-weight:800;letter-spacing:-.02em;white-space:nowrap}
.k-val i{font-style:normal;color:var(--acc);font-weight:600}
.kpi-hi .k-val{color:#fff}
.k-sub{font-size:13px;color:var(--mut)}

/* código y resultados */
details.codigo{margin:18px 0 10px}
details.codigo summary{cursor:pointer;display:inline-block;color:var(--mut);font-size:14px;font-weight:600;padding:6px 14px;border:1px dashed var(--line);border-radius:99px;transition:.2s;list-style:none}
details.codigo summary::-webkit-details-marker{display:none}
details.codigo summary:hover{color:#fff;border-color:var(--acc)}
details.codigo[open] summary{color:#fff;border-style:solid;background:var(--card2)}
pre{margin:12px 0 0;border-radius:14px;overflow-x:auto}
pre.hl{background:#1e1f1c;padding:18px 22px;font:13.5px/1.6 'JetBrains Mono',monospace;border:1px solid #333}
pre.stream{background:#060a18;border:1px solid var(--line);border-left:4px solid var(--acc);padding:14px 20px;font:14.5px/1.6 'JetBrains Mono',monospace;color:#c9f0dd;margin:12px 0}
.figura{background:#fff;border-radius:18px;padding:14px;margin:18px 0;box-shadow:0 20px 60px -30px #000}
.figura img{width:100%;display:block}
.hl .err{border:0}
{{PYGMENTS}}

/* conclusión en tarjetas */
#s4 ul{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:10px 0}
#s4 li{padding:22px 22px;background:#0e1631;border:1px solid var(--line);border-radius:18px;margin:0;font-size:16px}
#s4 li::before{display:none}
#s4 li:nth-child(1){border-top:4px solid var(--ok)}
#s4 li:nth-child(2){border-top:4px solid var(--acc)}
#s4 li:nth-child(3){border-top:4px solid var(--gold)}
#s4 li strong:first-child{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);background:none;margin-bottom:6px;padding:0}

footer{padding:30px 0 60px;text-align:center;color:var(--mut);font-size:14px}

@media (max-width:860px){
  .card{padding:24px 20px;border-radius:20px}.kpis{grid-template-columns:1fr 1fr}#s4 ul{grid-template-columns:1fr}
  .card h2{font-size:24px}.hero{padding-top:44px}
}
@media print{.nav{display:none}body{background:#fff;color:#000}}
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
