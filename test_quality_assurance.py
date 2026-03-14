
import pytest
import os
import re
import json

def test_no_cacophony_in_dashboard():
    dashboard_path = "/home/gorops/proyectos antigravity/zohar-agent/dashboard/index.html"
    if not os.path.exists(dashboard_path):
        pytest.skip("Dashboard file not found")
        
    with open(dashboard_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Regex para detectar & o y seguido de espacio e 'i'
    # Excluimos casos donde la 'i' es parte de un diptongo como 'ia', 'ie' (ej. 'y hierro', 'y ia') 
    # pero el usuario fue estricto con 'i' solo.
    # Buscamos patrones como "& inteligencia", "y integridad", "& investigación"
    cacophony_pattern = r"\s+[&y]\s+i[n|m|l|d|r|s|t|v]" 
    matches = re.findall(cacophony_pattern, content.lower())
    
    assert len(matches) == 0, f"Se encontró cacofonía: {matches}"

def test_correct_conjunction_in_dashboard():
    dashboard_path = "/home/gorops/proyectos antigravity/zohar-agent/dashboard/index.html"
    with open(dashboard_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Verificamos que diga "Inteligencia e Integridad"
    assert "Inteligencia e Integridad" in content

def test_vercel_proxy_sync():
    root = "/home/gorops/proyectos antigravity/zohar-agent"
    vercel_path = os.path.join(root, "vercel.json")
    tunnel_path = os.path.join(root, "tunnel_url.txt")
    
    if not os.path.exists(tunnel_path):
        pytest.skip("tunnel_url.txt not found")
    
    with open(tunnel_path, "r") as f:
        tunnel_content = f.read()
        match = re.search(r"https?://[^\s]+", tunnel_content)
        current_tunnel = match.group(0).rstrip('/') if match else ""
    
    with open(vercel_path, "r") as f:
        vercel_config = json.load(f)
    
    # Buscar el primer rewrite que apunta al túnel (que empiece con http)
    proxy_dest = next((r["destination"] for r in vercel_config["rewrites"] if r["destination"].startswith("http")), "")
    
    assert current_tunnel in proxy_dest, f"Vercel proxy destination ({proxy_dest}) doesn't match current tunnel ({current_tunnel})"

def test_api_status_reachable():
    # Este test intenta contactar al tunnel actual
    root = "/home/gorops/proyectos antigravity/zohar-agent"
    tunnel_path = os.path.join(root, "tunnel_url.txt")
    
    if not os.path.exists(tunnel_path):
        pytest.skip("tunnel_url.txt not found")
        
    with open(tunnel_path, "r") as f:
        tunnel_content = f.read()
        match = re.search(r"https?://[^\s]+", tunnel_content)
        current_tunnel = match.group(0).rstrip('/') if match else ""
    
    if not current_tunnel:
        pytest.fail("No tunnel URL found in tunnel_url.txt")
    
    import urllib.request
    try:
        url = f"{current_tunnel}/api/status"
        # Bypassing localtunnel interstitial page
        req = urllib.request.Request(url, headers={'Bypass-Tunnel-Reminder': 'true'})
        with urllib.request.urlopen(req, timeout=10) as response:
            assert response.getcode() == 200
            data = json.loads(response.read().decode())
            assert "llama_ok" in data
    except Exception as e:
        pytest.fail(f"Could not reach API via tunnel {current_tunnel}: {e}")
