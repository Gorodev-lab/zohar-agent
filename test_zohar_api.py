
import pytest
import sys
import os
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Añadir directorio api al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "api")))
from zohar_api import app, is_valid_record

client = TestClient(app)

# ═══════════════════════════════════════════════════════════════════
# UNIT TESTS: is_valid_record
# ═══════════════════════════════════════════════════════════════════

class TestApiValidation:
    def test_valid_record_accepted(self):
        assert is_valid_record(
            "PLANTA SOLAR FOTOVOLTAICA",
            "ENERGIA LIMPIA S.A. DE C.V.",
            "http://source.com/doc.pdf"
        ) is True

    def test_placeholder_rejected(self):
        assert is_valid_record(
            "Proyecto de inversión", # Placeholder term
            "DESCONOCIDO",           # Forbidden pattern
            "http://source.com"
        ) is False

    def test_short_name_rejected(self):
        assert is_valid_record("Abc", "Ese", "http://ok.com") is False

    def test_missing_source_rejected(self):
        assert is_valid_record("VALID PROJECT NAME LONG ENOUGH", "VALID PROMOVENTE", "no-link") is False

# ═══════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Endpoints
# ═══════════════════════════════════════════════════════════════════

class TestApiEndpoints:
    @patch("zohar_api.load_audited_data")
    def test_get_projects(self, mock_load):
        # Mock data
        mock_load.return_value = MagicMock()
        mock_load.return_value.fillna.return_value.to_dict.return_value = [
            {"ID_PROYECTO": "23QR2025T001", "ANIO": "2025"}
        ]
        
        response = client.get("/api/projects")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["ID_PROYECTO"] == "23QR2025T001"

    def test_get_status(self):
        with patch("zohar_api._check_service", return_value=(True, "")):
            response = client.get("/api/status")
            assert response.status_code == 200
            assert response.json()["llama_ok"] is True

    @patch("sqlite3.connect")
    def test_post_audit(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        payload = {"pid": "TEST001", "status": "audited", "notes": "Todo ok"}
        response = client.post("/api/audit", json=payload)
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_conn.execute.assert_called()
