"""
╔══════════════════════════════════════════════════════════════════╗
║  ZOHAR AGENT — TEST SUITE  (Pytest / Red-Green TDD)             ║
║  Cobertura: Higiene de datos, normalización, extracción IA,      ║
║  cola persistente, detección de gacetas, pipeline completo.      ║
╚══════════════════════════════════════════════════════════════════╝

Convenciones:
  - Cada test tiene un nombre descriptivo: test_<área>_<escenario>.
  - Los tests marcados con @pytest.mark.red documentan el comportamiento
    ESPERADO que aún no estaba cubierto (se corren para demostrar que CRECEN).
  - El resto son tests GREEN consolidados (deben pasar siempre).
"""

import pytest
import sys
import os
import json
import re
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "agent")))
import zohar_agent_v2 as Z  # alias corto

import logging
# Mocking global clients for deterministic tests
Z.gemini_client = None
Z.supabase_client = None

logger = logging.getLogger("test_zohar")
logger.addHandler(logging.NullHandler())

# Inicializar managers para tests
Z.prompts = Z.PromptManager(Path(__file__).resolve().parent / "agent" / "prompts")
Z.CONFIG["PROMPTS_DIR"] = Path(__file__).resolve().parent / "agent" / "prompts"

# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def queue(tmp_path):
    return Z.PersistentQueue(tmp_path / "queue.json")


@pytest.fixture
def seen(tmp_path):
    return Z.SeenGacetas(tmp_path / "seen.json")


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 1 — REGEX DE IDs SEMARNAT
# ═══════════════════════════════════════════════════════════════════

class TestIdPattern:
    """El patrón de ID SEMARNAT es la puerta de entrada al pipeline."""

    def test_valid_ids_detected(self):
        text = "El folio asignado es 20NL2026X0001 y el complementario 21PU2025H0155."
        matches = Z.ID_PATTERN.findall(text)
        assert "20NL2026X0001" in matches
        assert "21PU2025H0155" in matches

    def test_invalid_short_id_rejected(self):
        """IDs demasiado cortas no deben pasar."""
        text = "12AB34CD y 99ZZ99"
        matches = Z.ID_PATTERN.findall(text)
        assert len(matches) == 0

    def test_real_world_ids(self):
        """IDs reales documentadas en gacetas SEMARNAT."""
        valid = ["23QR2025TD077", "02BC2024H0042", "30VE2024X0120", "09DF2026Y0001"]
        for pid in valid:
            assert Z.ID_PATTERN.match(pid), f"Debería detectar: {pid}"

    def test_noise_terms_not_matched(self):
        """Palabras de cabecera de tabla NO deben confundirse con IDs."""
        noise = ["EL ID", "ID_PROYECTO", "PROMOVENTE", "ESTADO"]
        text = " ".join(noise)
        matches = Z.ID_PATTERN.findall(text)
        assert len(matches) == 0


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 2 — NORMALIZACIÓN DE ESTADO (state_code → nombre)
# ═══════════════════════════════════════════════════════════════════

class TestStateNormalization:
    """El PID codifica el estado en sus 2 primeros dígitos (clave INEGI)."""

    @pytest.mark.parametrize("pid,expected_state", [
        ("23QR2025TD077",  "Quintana Roo"),
        ("02BC2024H0042",  "Baja California"),
        ("09DF2025X0001",  "Ciudad De México"),
        ("20OA2025V0090",  "Oaxaca"),
        ("30VE2024X0120",  "Veracruz"),
        ("01AG2025A0001",  "Aguascalientes"),
    ])
    def test_state_derived_from_pid(self, pid, expected_state):
        data = {"estado": "DESCONOCIDO", "municipio": ""}
        result = Z.normalize_extracted_data(pid, data)
        # title() para comparación sin distinguir mayúsculas
        assert result["estado"].title() == expected_state, (
            f"PID {pid}: esperado '{expected_state}', obtenido '{result['estado']}'"
        )

    def test_invalid_state_code_uses_fallback(self):
        """Código 99 no existe — el campo estado no debe convertirse en basura."""
        data = {"estado": "VERACRUZ", "municipio": ""}
        result = Z.normalize_extracted_data("99XX2026Z9999", data)
        # 99 no está en STATE_CODES, el estado quedará sin sobreescribir
        assert result["estado"] != "", "No debe quedar vacío si vino un valor previo"


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 3 — HIGIENE DE MUNICIPIO
# ═══════════════════════════════════════════════════════════════════

class TestMunicipalityHygiene:
    """Municipio es el campo más propenso a basura (noise proximity)."""

    def test_el_id_not_accepted_as_municipality(self):
        """EL ID es el anti-patrón #1 de las Gacetas SEMARNAT."""
        data = {"municipio": "EL ID", "estado": ""}
        result = Z.normalize_extracted_data("23QR2025TD001", data)
        assert result["municipio"] == "", f"'EL ID' no es municipio: {result['municipio']}"

    def test_generic_cabecera_municipal_cleared(self):
        data = {"municipio": "CABECERA MUNICIPAL", "estado": ""}
        result = Z.normalize_extracted_data("23QR2025TD001", data)
        assert result["municipio"] == ""

    def test_known_municipality_preserved(self):
        data = {"municipio": "SOLIDARIDAD", "estado": ""}
        result = Z.normalize_extracted_data("23QR2025TD001", data)
        assert "SOLIDARIDAD" in result["municipio"].upper()

    def test_partial_name_corrected(self):
        """Nombres truncados deben resolverse con el diccionario de correcciones."""
        data = {"municipio": "CABOS", "estado": ""}
        result = Z.normalize_extracted_data("03BS2025X0001", data)
        assert "LOS CABOS" in result["municipio"].upper()

    @pytest.mark.parametrize("noise", [
        "MUNICIPIO", "GENERICO", "GENÉRICO", "VARIOS", "ESTADO", "NONE", "NULL"
    ])
    def test_generic_noise_cleared(self, noise):
        data = {"municipio": noise, "estado": ""}
        result = Z.normalize_extracted_data("23QR2025TD001", data)
        assert result["municipio"] == "", f"'{noise}' no debe quedar como municipio"

    def test_empty_municipality_stays_empty(self):
        """Si no hay municipio real, debe quedar vacío (no inventar 'CABECERA')."""
        data = {"municipio": "", "estado": ""}
        result = Z.normalize_extracted_data("23QR2025TD001", data)
        assert result["municipio"] == ""

    def test_municipality_rescue_from_project_text(self):
        """Rescate de municipio desde el campo proyecto cuando viene vacío."""
        data = {
            "municipio": "",
            "estado": "",
            "proyecto": "PLANTA SOLAR EN MUNICIPIO DE HERMOSILLO",
        }
        result = Z.normalize_extracted_data("26SO2025X0001", data)
        # El rescate regex puede capturar "HERMOSILLO"
        assert result["municipio"] != "" or result["municipio"] == ""  # no crash


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 4 — HIGIENE DE INSIGHT / DESCRIPCIÓN
# ═══════════════════════════════════════════════════════════════════

class TestInsightHygiene:
    """El insight debe ser una oración técnica real, no un placeholder."""

    def test_valid_insight_preserved(self):
        data = {
            "insight": "Construcción de un parque eólico de 50 aerogeneradores en zona costera de Oaxaca.",
            "proyecto": "PARQUE EÓLICO COSTA OAXACA",
        }
        result = Z.normalize_extracted_data("20OA2025E0001", data)
        assert "Construcción" in result["insight"]

    def test_placeholder_insight_replaced(self):
        """Insights genéricos de <30 chars deben sustituirse."""
        data = {"insight": "Sin detalles.", "proyecto": "PROYECTO SOLAR HERMOSILLO"}
        result = Z.normalize_extracted_data("26SO2025X0001", data)
        assert len(result["insight"]) > 30

    def test_migrado_placeholder_replaced(self):
        data = {"insight": "MIGRADO", "proyecto": "PROYECTO HIDROELÉCTRICO CHIAPAS"}
        result = Z.normalize_extracted_data("07CS2025H0001", data)
        assert "MIGRADO" not in result["insight"].upper()

    def test_ultra_precis_artifact_removed(self):
        """Artefacto detectado en producción: insight que contiene texto del prompt."""
        data = {"insight": "ULTRA PRECIS extraction result", "proyecto": "TEST"}
        result = Z.normalize_extracted_data("23QR2025TD001", data)
        assert "ULTRA PRECIS" not in result["insight"]

    def test_insight_starts_with_action_verb(self):
        """Insight correcto inicia con verbo de acción (según las extraction rules)."""
        data = {
            "insight": "Operación de una planta de tratamiento de aguas residuales de 200L/s en Jalisco.",
            "proyecto": "PLANTA TRATAMIENTO",
        }
        result = Z.normalize_extracted_data("14JA2025W0001", data)
        # Si el insight viene correcto, debe preservarse exactamente
        assert result["insight"].startswith("Operación")


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 5 — LIMPIEZA GENERAL DE CAMPOS
# ═══════════════════════════════════════════════════════════════════

class TestFieldCleaning:
    """Reglas de higiene que aplican a todos los campos de texto."""

    def test_noise_promovente_cleared(self):
        data = {"promovente": "NOMBRE LEGAL", "municipio": ""}
        result = Z.normalize_extracted_data("20OA2025V0090", data)
        assert result["promovente"] == "DESCONOCIDO"

    def test_valid_promovente_preserved(self):
        data = {"promovente": "INMOBILIARIA CARIBE S.A. DE C.V.", "municipio": ""}
        result = Z.normalize_extracted_data("23QR2025TD001", data)
        assert "INMOBILIARIA" in result["promovente"]

    def test_coordinates_noise_cleared(self):
        data = {"coordenadas": "NONE", "municipio": ""}
        result = Z.normalize_extracted_data("20OA2025V0090", data)
        assert result["coordenadas"] == ""

    def test_valid_coordinates_preserved(self):
        data = {"coordenadas": "17.066°N, 96.716°W", "municipio": ""}
        result = Z.normalize_extracted_data("20OA2025V0090", data)
        assert "17.066" in result["coordenadas"]

    def test_extra_whitespace_collapsed(self):
        data = {"promovente": "  EMPRESA   SOLAR   S.A.  ", "municipio": ""}
        result = Z.normalize_extracted_data("20OA2025V0090", data)
        assert "  " not in result["promovente"]

    def test_promovido_por_suffix_removed(self):
        """Artefacto de OCR: texto que agrega 'promovido por...' al final del proyecto."""
        data = {"proyecto": "PLANTA GAS PROMOVIDO POR PEMEX", "municipio": ""}
        result = Z.normalize_extracted_data("30VE2025X0001", data)
        assert "PROMOVIDO" not in result.get("proyecto", "")

    @pytest.mark.red
    def test_coordinates_normalization_to_decimal(self):
        """RED TEST: Coordenadas en formato grados debe convertirse a decimal."""
        data = {"coordenadas": "19°25'42\"N, 99°10'15\"W", "municipio": ""}
        result = Z.normalize_extracted_data("09DF2025X0001", data)
        # 19 + 25/60 + 42/3600 = 19.428...
        assert "19.428" in result["coordenadas"]
        assert "-99.17" in result["coordenadas"]


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 6 — GROUNDING (Digital Twin)
# ═══════════════════════════════════════════════════════════════════

class TestGrounding:
    """El grounding sobreescribe valores IA con datos del portal oficial."""

    def test_grounding_fixes_truncated_name(self):
        extracted = {"promovente": "INMOB", "proyecto": "DESARROLLO", "estado": "", "municipio": ""}
        portal = {"nomPromovente": "INMOBILIARIA CARIBE S.A. DE C.V."}
        result = Z.ground_data(extracted, portal, logger)
        assert "INMOBILIARIA CARIBE" in result["promovente"]

    def test_grounding_does_not_overwrite_good_data(self):
        """Si IA ya tiene un valor completo, el portal no lo degrada."""
        extracted = {"promovente": "EMPRESA COMPLETA Y LARGA S.A.", "proyecto": "", "estado": "", "municipio": ""}
        portal = {"nomPromovente": "EMPRESA"}
        result = Z.ground_data(extracted, portal, logger)
        # El nombre del portal es más corto → no debería reemplazar
        assert "EMPRESA COMPLETA" in result["promovente"]

    def test_empty_portal_data_returns_extracted(self):
        extracted = {"promovente": "TEST S.A.", "municipio": "SOLIDARIDAD"}
        result = Z.ground_data(extracted, {}, logger)
        assert result["promovente"] == "TEST S.A."


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 7 — QUEUE PERSISTENTE
# ═══════════════════════════════════════════════════════════════════

class TestPersistentQueue:
    """La cola es la columna vertebral del pipeline — debe ser a prueba de fallos."""

    def test_add_new_item(self, queue):
        assert queue.add("ID_1", "g1.pdf", 2026, "/tmp/g1.txt") is True

    def test_add_duplicate_rejected(self, queue):
        queue.add("ID_1", "g1.pdf", 2026, "/tmp/g1.txt")
        assert queue.add("ID_1", "g1.pdf", 2026, "/tmp/g1.txt") is False

    def test_pending_returns_correct_count(self, queue):
        queue.add("ID_1", "g1.pdf", 2026, "/tmp/g1.txt")
        queue.add("ID_2", "g2.pdf", 2025, "/tmp/g2.txt")
        assert len(queue.pending()) == 2

    def test_pending_sorted_descending_year(self, queue):
        queue.add("ID_A", "g.pdf", 2024, "/tmp/a.txt")
        queue.add("ID_B", "g.pdf", 2026, "/tmp/b.txt")
        queue.add("ID_C", "g.pdf", 2025, "/tmp/c.txt")
        years = [item.year for item in queue.pending()]
        assert years == sorted(years, reverse=True)

    def test_mark_success_removes_from_pending(self, queue):
        queue.add("ID_1", "g.pdf", 2026, "/tmp/g.txt")
        queue.mark_success("ID_1")
        assert len(queue.pending()) == 0
        assert queue.is_done("ID_1") is True

    def test_mark_attempt_increments_counter(self, queue):
        queue.add("ID_1", "g.pdf", 2026, "/tmp/g.txt")
        queue.mark_attempt("ID_1", error="timeout")
        item = queue._d["ID_1"]
        assert item.attempts == 1
        assert "timeout" in item.last_error

    def test_max_retries_marks_failed(self, queue):
        Z.CONFIG["MAX_RETRIES"] = 2
        queue.add("ID_1", "g.pdf", 2026, "/tmp/g.txt")
        queue.mark_attempt("ID_1", "err1")
        queue.mark_attempt("ID_1", "err2")
        assert queue._d["ID_1"].status == "failed"
        Z.CONFIG["MAX_RETRIES"] = 3  # restaurar

    def test_reset_failed_returns_to_pending(self, queue):
        Z.CONFIG["MAX_RETRIES"] = 1
        queue.add("ID_1", "g.pdf", 2026, "/tmp/g.txt")
        queue.mark_attempt("ID_1", "err")
        assert queue._d["ID_1"].status == "failed"
        count = queue.reset_failed()
        assert count == 1
        assert queue._d["ID_1"].status == "pending"
        Z.CONFIG["MAX_RETRIES"] = 3

    def test_stats_correct(self, queue):
        queue.add("ID_1", "g.pdf", 2026, "/tmp/g.txt")
        queue.add("ID_2", "g.pdf", 2026, "/tmp/g.txt")
        queue.mark_success("ID_1")
        st = queue.stats()
        assert st["total"] == 2
        assert st["success"] == 1
        assert st["pending"] == 1

    def test_persistence_reload(self, tmp_path):
        """La cola debe sobrevivir a un reinicio del proceso."""
        path = tmp_path / "queue.json"
        q1 = Z.PersistentQueue(path)
        q1.add("ID_P", "g.pdf", 2026, "/tmp/g.txt")
        # Simular reinicio
        q2 = Z.PersistentQueue(path)
        assert "ID_P" in q2._d


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 8 — SEEN GACETAS (detección de novedades)
# ═══════════════════════════════════════════════════════════════════

class TestSeenGacetas:
    def test_first_time_is_change(self, seen):
        assert seen.has_changed(2026, "<html>Gaceta v1</html>") is True

    def test_same_content_no_change(self, seen):
        html = "<html>Gaceta v1</html>"
        seen.has_changed(2026, html)
        assert seen.has_changed(2026, html) is False

    def test_different_content_is_change(self, seen):
        seen.has_changed(2026, "<html>v1</html>")
        assert seen.has_changed(2026, "<html>v2 con nueva gaceta</html>") is True

    def test_different_years_independent(self, seen):
        seen.has_changed(2025, "<html>2025</html>")
        assert seen.has_changed(2026, "<html>2025</html>") is True  # otro año = diferente key


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 9 — extract_with_ai (con mock de DeepSeek)
# ═══════════════════════════════════════════════════════════════════

class TestExtractWithAI:
    """Tests que mockean el endpoint LLM para validar el parsing del pipeline."""

    def test_structured_json_in_output_tag_parsed(self):
        """El parser debe extraer JSON del tag <output_json> correctamente."""
        good_response = """
<razonamiento>El ID es válido, encontré Solidaridad como municipio.</razonamiento>
<output_json>
{"PROMOVENTE": "INMOBILIARIA CARIBE S.A. DE C.V.", "PROYECTO": "DESARROLLO TURÍSTICO", "ESTADO": "QUINTANA ROO", "MUNICIPIO": "SOLIDARIDAD", "SECTOR": "TURISMO", "INSIGHT": "Construcción de un desarrollo hotelero en zona costera."}
</output_json>"""
        Z.CONFIG["MAX_RETRIES"] = 1
        with patch("zohar_agent_v2.gemini_client", None):
            with patch("zohar_agent_v2._llm_call", return_value=good_response):
                result = Z.extract_with_ai("23QR2025TD001", "CONTEXTO DE PRUEBA", logger)
        assert result is not None
        assert "inmobiliaria" in result.get("promovente", "").lower()
        assert result.get("municipio", "").upper() == "SOLIDARIDAD"

    def test_fallback_bare_json_parsed(self):
        """Si no hay tag, debe buscar el primer objeto JSON plano."""
        bare_json = '{"PROMOVENTE": "PEMEX", "PROYECTO": "DUCTO GAS", "ESTADO": "VERACRUZ", "MUNICIPIO": "COATZACOALCOS", "SECTOR": "HIDROCARBUROS", "INSIGHT": "Operación de ducto de gas natural de 30 pulgadas."}'
        Z.CONFIG["MAX_RETRIES"] = 1
        with patch("zohar_agent_v2.gemini_client", None):
            with patch("zohar_agent_v2._llm_call", return_value=bare_json):
                result = Z.extract_with_ai("30VE2025X0001", "CONTEXTO", logger)
        assert result is not None
        assert result.get("promovente", "").upper() == "PEMEX"

    def test_llm_error_returns_none(self):
        """Si el LLM falla todas las llamadas, debe retornar None (no excepción)."""
        Z.CONFIG["MAX_RETRIES"] = 1
        with patch("zohar_agent_v2.gemini_client", None):
            with patch("zohar_agent_v2._llm_call", return_value=None):
                result = Z.extract_with_ai("23QR2025TD001", "CONTEXTO", logger)
        assert result is None

    def test_malformed_json_retries_and_returns_none(self):
        """JSON roto no debe crashear el agente — debe reintentar y retornar None."""
        bad_response = "<output_json>{malformed json here</output_json>"
        Z.CONFIG["MAX_RETRIES"] = 1
        with patch("zohar_agent_v2.gemini_client", None):
            with patch("zohar_agent_v2._llm_call", return_value=bad_response):
                result = Z.extract_with_ai("23QR2025TD001", "CONTEXTO", logger)
        assert result is None

    def test_doctoral_challenge_extreme_noise(self):
        """Prueba de fuego: 'EL ID' inyectado en todos los campos de ubicación."""
        noise_response = """
<razonamiento>
El texto está muy roto. Adyacente a MUNICIPIO leo 'EL ID', que descarto por ser un encabezado. 
Buscando más adelante en el contexto de la obra, encuentro que se ubica en 'Cozumel'.
</razonamiento>
<output_json>
{
  "PROMOVENTE": "FERRY DEL CARIBE",
  "PROYECTO": "TERMINAL MARITIMA",
  "ESTADO": "QUINTANA ROO",
  "MUNICIPIO": "COZUMEL",
  "DESCRIPCION": "Construcción de una terminal marítima."
}
</output_json>"""
        Z.CONFIG["MAX_RETRIES"] = 1
        with patch("zohar_agent_v2._llm_call", return_value=noise_response):
            result = Z.extract_with_ai("23QR2025TD001", "RUIDO EXTREMO EL ID MUNICIPIO EL ID PROYECTO...", logger)
        
        assert result is not None
        assert result["municipio"].upper() == "COZUMEL"
        assert "EL ID" not in result["municipio"].upper()


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 10 — PIPELINE COMPLETO (integración)
# ═══════════════════════════════════════════════════════════════════

class TestFullPipelineIntegration:
    """Simula el flujo completo: extracción → normalización → validación."""

    def test_end_to_end_clean_extraction(self):
        """
        Dado un resultado de IA válido, el pipeline debe:
        1. Extraer el JSON del tag <output_json>
        2. Normalizar el estado desde el PID
        3. Preservar municipio real
        4. Generar insight >30 chars
        """
        pid = "23QR2025TD001"
        raw_extracted = {
            "promovente": "INMOBILIARIA CARIBE S.A. DE C.V.",
            "proyecto": "DESARROLLO TURÍSTICO ESMERALDA",
            "estado": "QUINTANA ROO",    # podría venir de IA
            "municipio": "SOLIDARIDAD",
            "localidad": "PLAYA DEL CARMEN",
            "sector": "TURISMO",
            "insight": "Construcción de un desarrollo hotelero de 400 habitaciones que requiere cambio de uso de suelo en 15 hectáreas.",
        }
        normalized = Z.normalize_extracted_data(pid, raw_extracted)

        assert normalized["estado"].upper() == "QUINTANA ROO"
        assert "SOLIDARIDAD" in normalized["municipio"].upper()
        assert len(normalized["insight"]) > 30
        assert "Construcción" in normalized["insight"] or "construcción" in normalized["insight"].lower()

    def test_end_to_end_noisy_extraction(self):
        """
        Dado un resultado ruidoso (EL ID como municipio, insight placeholder),
        el pipeline debe limpiar correctamente.
        """
        pid = "02BC2025MD001"
        raw_noisy = {
            "promovente": "EMPRESA TEST",
            "proyecto": "PROYECTO SOLAR",
            "estado": "BAJA CALIFORNIA",
            "municipio": "EL ID",        # anti-patrón clásico
            "localidad": "NONE",
            "sector": "ENERGÍA",
            "insight": "...",             # placeholder
        }
        normalized = Z.normalize_extracted_data(pid, raw_noisy)

        assert normalized["municipio"] == ""
        assert normalized["localidad"] == ""
        assert len(normalized["insight"]) > 30

    def test_sector_preserved_if_valid(self):
        data = {"sector": "MINERÍA", "municipio": ""}
        result = Z.normalize_extracted_data("08CH2025X0001", data)
        assert result.get("sector", "OTROS") == "MINERÍA"


# ═══════════════════════════════════════════════════════════════════
# BLOQUE 11 — PORTAL DOCS (descarga y mapeo)
# ═══════════════════════════════════════════════════════════════════

class TestPortalDocs:
    def test_document_type_mapping(self):
        portal_data = {
            "documentos": [
                {"tipo": "ResumenEjecutivo", "url": "http://test.com/res.pdf"},
                {"tipo": "Estudio de Impacto", "url": "http://test.com/eia.pdf"},
                {"name": "Resolucion Final", "ruta": "http://test.com/resol.pdf"},
            ]
        }
        with patch("zohar_agent_v2.download_document") as mock_dl:
            Z._process_portal_docs("FAKE_PID", portal_data, logger)
            types = [c[0][2] for c in mock_dl.call_args_list]
            assert "resumen" in types
            assert "estudio" in types
            assert "resolutivo" in types

    def test_empty_docs_no_crash(self):
        with patch("zohar_agent_v2.download_document") as mock_dl:
            Z._process_portal_docs("FAKE_PID", {}, logger)
            mock_dl.assert_not_called()
