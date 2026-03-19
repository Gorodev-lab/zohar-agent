# AI Model Strategy & Performance Optimization

## 1. Tiered Intelligence Architecture
To reduce Gemini costs and local resource impact, we will implement a 3-tier routing strategy.

| Tier | Task Type | Recommended Model | Strategy |
| :--- | :--- | :--- | :--- |
| **Tier 1 (Local)** | Relevance check, pre-filtering, basic classification | **Mistral-7B / Qwen-1.5B** | Filter out 80% of irrelevant project metadata before hitting cloud. |
| **Tier 2 (Cloud-Lite)** | Standard extraction, JSON formatting | **Gemini-1.5-Flash** | Low latency, highly structured output, cheaper than Pro. |
| **Tier 3 (Cloud-Deep)** | Complex legal analysis, risk auditing, full MIA extraction | **Gemini-1.5-Pro / DeepSeek-V3** | Use only for top 10% high-priority projects. |

## 2. Resource & Performance Guardrails
- **Log Rotation:** Limit `zohar_agent.jsonl` to 50MB with automatic pruning (Now active).
- **Process Throttling:** Load-based sleep implemented (POLL_INTERVAL_MIN doubles if load > 4.0).
- **Memory Management:** Monitor RAM usage via Dashboard Diagnostics.

## 3. Gemini Account & Project Transparency
- Dashboard /diagnostics tab shows active key prefix and account info.
- Log journey for each project includes cost estimation and model used.
