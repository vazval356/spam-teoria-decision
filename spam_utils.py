"""Funciones auxiliares del trabajo. Las matemáticas son las del temario (tema 6):
z = Xw, y = sigmoide(z), pérdida BCE + L2, gradiente X^T(y - t)/N + 2·lambda·w, descenso de gradiente."""
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split

SEMILLA = 42

NOMBRES = [f"word_freq_{w}" for w in
           ["make", "address", "all", "3d", "our", "over", "remove", "internet", "order", "mail",
            "receive", "will", "people", "report", "addresses", "free", "business", "email", "you",
            "credit", "your", "font", "000", "money", "hp", "hpl", "george", "650", "lab", "labs",
            "telnet", "857", "data", "415", "85", "technology", "1999", "parts", "pm", "direct", "cs",
            "meeting", "original", "project", "re", "edu", "table", "conference"]]
NOMBRES += [f"char_freq_{c}" for c in [";", "(", "[", "!", "$", "#"]]
NOMBRES += ["capital_run_length_average", "capital_run_length_longest", "capital_run_length_total"]


# ---------- Datos ----------
def cargar_y_limpiar(ruta="data/spambase.data"):
    """Carga Spambase, quita filas idénticas con etiqueta contradictoria y deja una copia de cada repetida."""
    datos = pd.read_csv(Path(ruta), header=None, names=NOMBRES + ["spam"])
    n_clases = datos.groupby(NOMBRES)["spam"].transform("nunique")
    limpio = datos[n_clases == 1].drop_duplicates()
    return limpio[NOMBRES].to_numpy(float), limpio["spam"].to_numpy(int), len(datos)


def partir(X, t):
    """60 % entrenamiento, 20 % validación, 20 % prueba, con la misma proporción de spam."""
    X_tmp, X_te, t_tmp, t_te = train_test_split(X, t, test_size=0.2, stratify=t, random_state=SEMILLA)
    X_tr, X_va, t_tr, t_va = train_test_split(X_tmp, t_tmp, test_size=0.25, stratify=t_tmp, random_state=SEMILLA)
    return X_tr, X_va, X_te, t_tr, t_va, t_te


def preparar(X_tr, *otros):
    """log(1+x) y z-score ajustados SOLO con entrenamiento; añade la columna de unos (sesgo)."""
    media, desv = np.log1p(X_tr).mean(0), np.log1p(X_tr).std(0)
    return [np.hstack([(np.log1p(A) - media) / desv, np.ones((len(A), 1))]) for A in (X_tr,) + otros]


# ---------- Modelo: regresión logística por descenso de gradiente ----------
def sigmoide(z):
    return 1 / (1 + np.exp(-z))


def bce(t, y):
    y = np.clip(y, 1e-12, 1 - 1e-12)
    return -np.mean(t * np.log(y) + (1 - t) * np.log(1 - y))


def entrenar(A, t, lam=0.0, alpha=0.5, iteraciones=3000):
    w = np.zeros(A.shape[1])
    for _ in range(iteraciones):
        y = sigmoide(A @ w)
        grad = A.T @ (y - t) / len(t) + 2 * lam * np.r_[w[:-1], 0]   # el sesgo no se regulariza
        w -= alpha * grad
    return w


# ---------- Evaluación ----------
def evaluar(t, p, umbral, c_fp=10, c_fn=1):
    spam = p >= umbral
    VP, FN = int(np.sum(spam & (t == 1))), int(np.sum(~spam & (t == 1)))
    FP, VN = int(np.sum(spam & (t == 0))), int(np.sum(~spam & (t == 0)))
    return {"FP (legítimos perdidos)": FP, "FN (spam que se cuela)": FN,
            "acierto": (VP + VN) / len(t), "coste": c_fp * FP + c_fn * FN}


def auc(t, p):
    """Probabilidad de que un spam puntúe más que un legítimo."""
    pos, neg = p[t == 1], p[t == 0]
    return np.mean(pos[:, None] > neg[None, :]) + 0.5 * np.mean(pos[:, None] == neg[None, :])


def curva_calibracion(t, p, grupos=10):
    g = np.minimum((p * grupos).astype(int), grupos - 1)
    pares = [(p[g == k].mean(), t[g == k].mean()) for k in range(grupos) if np.sum(g == k) >= 5]
    return np.array(pares).T


def bootstrap_ahorro(t, p, r, B=2000, semilla=SEMILLA, porcentaje=False):
    """Intervalo del 95 % del ahorro (coste con 0,5 menos coste con t*) remuestreando la prueba."""
    def coste_correo(u):
        spam = p >= u
        return r * (spam & (t == 0)) + (~spam & (t == 1))
    c05 = coste_correo(0.5)
    a = c05 - coste_correo(r / (r + 1))
    idx = np.random.default_rng(semilla).integers(0, len(a), size=(B, len(a)))
    if not porcentaje:
        return a.sum(), np.percentile(a[idx].sum(1), [2.5, 97.5])
    # % de ahorro calculado dentro de cada remuestreo (así nunca pasa del 100 %)
    return 100 * a.sum() / c05.sum(), np.percentile(100 * a[idx].sum(1) / c05[idx].sum(1), [2.5, 97.5])
