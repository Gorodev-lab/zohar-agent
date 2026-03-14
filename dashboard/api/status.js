export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS');
  res.status(200).json({
    "cpu_temp": "Cloud",
    "llama_status": "Serverless (Hybrid)",
    "agent_running": true,
    "llama_ok": true,
    "mode": "serverless-first"
  });
}
