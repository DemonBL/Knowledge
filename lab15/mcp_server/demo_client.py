"""ЛР15 · демо MCP-клієнта: підключення до mcp_server/server.py через stdio, список інструментів і 3 виклики → results/mcp_demo.json."""
import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

LAB = Path(__file__).resolve().parents[1]


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(LAB / "mcp_server" / "server.py")], env={"HUB_ROLE": "guest", "PYTHONIOENCODING": "utf-8"})
    out = {"calls": []}
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            info = await s.initialize()
            si = getattr(info, "server_info", None) or getattr(info, "serverInfo")
            out["server"] = {"name": si.name, "protocol": getattr(info, "protocol_version", None) or getattr(info, "protocolVersion", "")}
            tl = await s.list_tools()
            ro = lambda a: None if a is None else (getattr(a, "read_only_hint", None) if hasattr(a, "read_only_hint") else getattr(a, "readOnlyHint", None))
            out["tools"] = [{"name": t.name, "readOnly": ro(t.annotations),
                             "schema": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None)} for t in tl.tools]
            for name, args in [("kb_graph", {"query_type": "claim", "entity": "CLM-13"}),
                               ("search_docs", {"query": "регламент вердикт фейк докази", "k": 3}),
                               ("olap_metrics", {"metrics": ["false_verdict_rate"], "dimensions": ["platform"]})]:
                t0 = time.perf_counter()
                res = await s.call_tool(name, args)
                txt = res.content[0].text
                out["calls"].append({"tool": name, "args": args, "latency_s": round(time.perf_counter() - t0, 3), "result": json.loads(txt)})
    (LAB / "results").mkdir(exist_ok=True)
    (LAB / "results" / "mcp_demo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"server": out["server"], "tools": [t["name"] for t in out["tools"]],
                      "calls": [(c["tool"], c["latency_s"], [x.get("id") for x in c["result"].get("results", [])]) for c in out["calls"]]}, ensure_ascii=False))


asyncio.run(main())
