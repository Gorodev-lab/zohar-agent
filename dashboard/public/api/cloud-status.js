export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
  res.status(200).json({
    "cpu_temp": "Nube",
    "llama_status": "Serverless (Híbrido)",
    "agent_running": true,
    "llama_ok": true,
    "mode": "prioridad-nube"
  });
}
