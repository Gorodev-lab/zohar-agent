"""
warehouse/transformers/normalizer.py
Normaliza campos: municipios, estados, trim, encoding.
"""
import re, logging

log = logging.getLogger("warehouse.normalizer")

STATE_ALIASES = {
    "MEX": "México", "CDMX": "Ciudad de México",
    "NL": "Nuevo León", "BC": "Baja California",
    "BCS": "Baja California Sur", "GRO": "Guerrero",
}


class Normalizer:
    def normalize(self, records: list[dict]) -> list[dict]:
        out = []
        for r in records:
            r = dict(r)
            r["municipio"] = self._clean(r.get("municipio", ""))
            r["estado"]    = self._clean(r.get("estado", ""))
            r["estado"]    = STATE_ALIASES.get(r["estado"], r["estado"])
            r["promovente"]= self._clean(r.get("promovente",""))
            # Asegurar pid
            if not r.get("pid"):
                continue
            out.append(r)
        log.debug(f"Normalizer: {len(out)}/{len(records)} registros OK")
        return out

    @staticmethod
    def _clean(s: str) -> str:
        if not s: return ""
        s = s.strip()
        s = re.sub(r'\s+', ' ', s)
        return s
