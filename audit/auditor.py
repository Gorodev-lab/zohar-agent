#!/usr/bin/env python3
"""
╔════════════════════════════════════════════════════════╗
║  ZOHAR — DATA QUALITY AUDITOR                        ║
║  audit/auditor.py                                    ║
║  Uso: python -m audit.run_audit [--year 2026]        ║
╚════════════════════════════════════════════════════════╝
"""
import os, sqlite3, json, logging
from pathlib import Path
from datetime import datetime, date

try:
    import pandas as pd
except ImportError:
    raise SystemExit("pandas requerido: pip install pandas")

log = logging.getLogger("audit.auditor")
DB_PATH      = Path.home() / "zohar_intelligence.db"
REPORTS_DIR  = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class DataAuditor:
    """
    Auditor de calidad de datos para zohar_intelligence.db.
    Genera un reporte Markdown con métricas de completitud,
    consistencia, frescura y cobertura de inteligencia.
    """

    def __init__(self, year: int | None = None):
        self.year  = year
        self.today = date.today().isoformat()

    # ── Carga ──────────────────────────────────────────────────────────────────
    def _load(self) -> pd.DataFrame:
        conn = sqlite3.connect(DB_PATH)
        query = "SELECT * FROM projects"
        params = []
        if self.year:
            query += " WHERE year = ?"; params.append(self.year)
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df

    # ── Checks ─────────────────────────────────────────────────────────────────
    def check_completeness(self, df: pd.DataFrame) -> dict:
        total = len(df)
        null_pct = (df.isnull().mean() * 100).round(1).to_dict()
        critical  = {k: v for k, v in null_pct.items() if v > 50}
        return {
            "total_rows":    total,
            "null_pct":      null_pct,
            "critical_cols": critical,   # >50% nulos
            "score":         round(100 - sum(null_pct.values()) / len(null_pct), 1)
        }

    def check_grounding(self, df: pd.DataFrame) -> dict:
        total     = len(df)
        grounded  = df["grounded"].sum() if "grounded" in df else 0
        with_coords = df["coordenadas"].notna().sum() if "coordenadas" in df else 0
        with_riesgo = df["riesgo_civil"].notna().sum() if "riesgo_civil" in df else 0  # puede no existir en SQLite
        return {
            "grounded_pct":    round(grounded  / total * 100, 1) if total else 0,
            "coords_pct":      round(with_coords / total * 100, 1) if total else 0,
            "riesgo_pct":      round(with_riesgo / total * 100, 1) if total else 0,
            "grounded_count":  int(grounded),
            "coords_count":    int(with_coords),
        }

    def check_consistency(self, df: pd.DataFrame) -> dict:
        issues = []
        # PIDs duplicados
        dupes = df[df.duplicated("pid", keep=False)]["pid"].unique().tolist()
        if dupes: issues.append(f"{len(dupes)} PIDs duplicados")
        # Años fuera de rango
        bad_years = df[(df["year"] < 2000) | (df["year"] > 2030)]["pid"].tolist()
        if bad_years: issues.append(f"{len(bad_years)} registros con año inválido")
        # Score fuera de rango
        if "confidence_score" in df.columns:
            bad_score = df[(df["confidence_score"] < 0) | (df["confidence_score"] > 100)]["pid"].tolist()
            if bad_score: issues.append(f"{len(bad_score)} registros con score fuera de [0,100]")
        return {
            "issues":    issues,
            "is_clean":  len(issues) == 0
        }

    def check_freshness(self, df: pd.DataFrame) -> dict:
        if "created_at" not in df.columns:
            return {"status": "sin timestamp"}
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        now = pd.Timestamp.now()
        df["age_days"] = (now - df["created_at"]).dt.days
        return {
            "oldest_days":  int(df["age_days"].max()),
            "newest_days":  int(df["age_days"].min()),
            "avg_age_days": round(df["age_days"].mean(), 1),
            "stale_count":  int((df["age_days"] > 30).sum()),   # >30 días
        }

    def check_by_year(self, df: pd.DataFrame) -> dict:
        return df.groupby("year").agg(
            count=("pid","count"),
            grounded=("grounded","sum"),
            avg_score=("confidence_score","mean")
        ).round(1).reset_index().to_dict(orient="records")

    def check_sectors(self, df: pd.DataFrame) -> dict:
        """
        One-hot encoding del campo 'sector' + groupby para
        calcular distribución de score y grounding por tipo de sector.
        Patrón: pd.get_dummies → mean/sum por feature codificada.
        """
        if "sector" not in df.columns or df["sector"].isna().all():
            return {}

        # 1. Limpiar y one-hot encode
        df_s = df[["pid", "sector", "confidence_score", "grounded"]].copy()
        df_s["sector"] = df_s["sector"].fillna("SIN_SECTOR").str.strip().str.upper()
        dummies = pd.get_dummies(df_s["sector"], prefix="sector")
        df_enc  = pd.concat([df_s, dummies], axis=1)

        # 2. Columnas codificadas
        sector_cols = [c for c in df_enc.columns if c.startswith("sector_")]

        # 3. Agregación: por cada sector, avg score y % grounded
        sector_cols_orig = df_enc["sector"].unique().tolist()
        result = (
            df_enc.groupby("sector")
            .agg(
                n_proyectos=("pid", "count"),
                avg_score=("confidence_score", "mean"),
                pct_grounded=("grounded", "mean"),
            )
            .round(2)
            .sort_values("n_proyectos", ascending=False)
            .reset_index()
            .rename(columns={"sector": "sector_nombre"})
            .to_dict(orient="records")
        )

        # 4. Correlación: qué sectores tienen mayor cobertura de grounding
        top_grounded = sorted(result, key=lambda r: r["pct_grounded"], reverse=True)

        return {
            "by_sector":  result,
            "top_grounded_sector": top_grounded[0]["sector_nombre"] if top_grounded else "—",
            "n_sectores": len(sector_cols_orig),
        }

    # ── Reporte ────────────────────────────────────────────────────────────────
    def _render_markdown(self, results: dict) -> str:
        c = results["completeness"]
        g = results["grounding"]
        k = results["consistency"]
        f = results["freshness"]

        # Semáforos
        def flag(pct): return "🟢" if pct >= 80 else ("🟡" if pct >= 50 else "🔴")

        lines = [
            f"# 🔍 Zohar — Reporte de Calidad de Datos",
            f"**Generado:** {self.today}  |  **Año filtro:** {self.year or 'todos'}",
            "",
            "---",
            "",
            "## 1️⃣ Completitud",
            f"- **Total registros:** {c['total_rows']}",
            f"- **Score general:** {c['score']}%",
            "",
            "| Columna | % Nulos | Estado |",
            "|---------|---------|--------|",
        ]
        for col, pct in sorted(c["null_pct"].items(), key=lambda x: -x[1]):
            estado = "🔴 CRÍTICO" if pct > 50 else ("🟡" if pct > 20 else "🟢")
            lines.append(f"| `{col}` | {pct}% | {estado} |")

        lines += [
            "",
            "## 2️⃣ Cobertura de Inteligencia",
            f"| Métrica | Valor | Estado |",
            f"|---------|-------|--------|",
            f"| Grounded (verificado web) | {g['grounded_count']} ({g['grounded_pct']}%) | {flag(g['grounded_pct'])} |",
            f"| Con coordenadas GPS       | {g['coords_count']} ({g['coords_pct']}%) | {flag(g['coords_pct'])} |",
            f"| Con riesgo civil          | — ({g['riesgo_pct']}%) | {flag(g['riesgo_pct'])} |",
            "",
            "## 3️⃣ Consistencia",
            f"- Estado: {'✅ Sin problemas' if k['is_clean'] else '⚠️ Problemas detectados'}",
        ]
        for issue in k["issues"]:
            lines.append(f"  - {issue}")

        lines += [
            "",
            "## 4️⃣ Frescura de Datos",
        ]
        if isinstance(f, dict) and "oldest_days" in f:
            lines += [
                f"- **Registro más antiguo:** {f['oldest_days']} días",
                f"- **Registro más reciente:** {f['newest_days']} días",
                f"- **Edad promedio:** {f['avg_age_days']} días",
                f"- **Registros obsoletos (>30d):** {f['stale_count']}",
            ]

        lines += [
            "",
            "## 5️⃣ Distribución por Año",
            "| Año | Registros | Grounded | Score Prom. |",
            "|-----|-----------|----------|-------------|",
        ]
        for row in results.get("by_year", []):
            lines.append(
                f"| {row['year']} | {row['count']} | {int(row['grounded'])} | {row['avg_score']:.1f} |"
            )

        # Sector distribution (one-hot + groupby)
        s = results.get("sectors", {})
        if s and s.get("by_sector"):
            lines += [
                "",
                f"## 6️⃣ Distribución por Sector ({s['n_sectores']} sectores)",
                f"*Sector con mayor cobertura de grounding: **{s['top_grounded_sector']}***",
                "",
                "| Sector | Proyectos | Score Prom. | % Grounded |",
                "|--------|-----------|-------------|------------|",
            ]
            for row in s["by_sector"]:
                lines.append(
                    f"| {row['sector_nombre']} | {row['n_proyectos']} "
                    f"| {row['avg_score']:.1f} | {row['pct_grounded']*100:.0f}% |"
                )

        lines += ["", "---", "*Zohar Data Quality Auditor // PRESERVE_INTEGRITY*"]
        return "\n".join(lines)

    # ── Run ────────────────────────────────────────────────────────────────────
    def run(self) -> dict:
        log.info("🔍 Iniciando auditoría de calidad de datos...")
        df = self._load()
        log.info(f"   {len(df)} registros cargados")

        results = {
            "generated_at":  datetime.now().isoformat(),
            "year_filter":   self.year,
            "completeness":  self.check_completeness(df),
            "grounding":     self.check_grounding(df),
            "consistency":   self.check_consistency(df),
            "freshness":     self.check_freshness(df),
            "by_year":       self.check_by_year(df),
            "sectors":       self.check_sectors(df),
        }

        # Guardar JSON detallado
        json_path = REPORTS_DIR / f"audit_{self.today}.json"
        json_path.write_text(json.dumps(results, indent=2, default=str))

        # Guardar Markdown legible
        md_path   = REPORTS_DIR / f"audit_{self.today}.md"
        md_path.write_text(self._render_markdown(results))

        log.info(f"✅ Reporte generado:")
        log.info(f"   📄 {md_path}")
        log.info(f"   📊 {json_path}")

        return results
