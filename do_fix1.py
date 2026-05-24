import sys
sys.stdout.reconfigure(encoding="utf-8")
r = open("src/agents/ai_router.py",encoding="utf-8").read()
start = r.find("            where = (")
end = r.find("            by_model = [")
old = r[start:end].rstrip()
new = (
    "            if date:\n"
    "                cursor = await conn.execute("""\n"
    "                    SELECT\n"
    "                      COUNT(*) AS calls,\n"
    "                      SUM(tokens_in) AS tok_in,\n"
    "                      SUM(tokens_out) AS tok_out,\n"
    "                      SUM(cost_usd) AS cost,\n"
    "                      AVG(latency_ms) AS lat,\n"
    "                      SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok,\n"
    "                      SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS fail\n"
    "                    FROM ai_usage WHERE DATE(created_at) = ?\n"
    "                """, (date,))\n"
    "                row = await cursor.fetchone()\n"
    "                cursor2 = await conn.execute("""\n"
    "                    SELECT model, COUNT(*) AS c, SUM(cost_usd) AS cost_sum\n"
    "                    FROM ai_usage WHERE DATE(created_at) = ?\n"
    "                    GROUP BY model ORDER BY c DESC\n"
    "                """, (date,))\n"
    "            else:\n"
    "                cursor = await conn.execute("""\n"
    "                    SELECT\n"
    "                      COUNT(*) AS calls,\n"
    "                      SUM(tokens_in) AS tok_in,\n"
    "                      SUM(tokens_out) AS tok_out,\n"
    "                      SUM(cost_usd) AS cost,\n"
    "                      AVG(latency_ms) AS lat,\n"
    "                      SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok,\n"
    "                      SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS fail\n"
    "                    FROM ai_usage WHERE DATE(created_at) = DATE("now")\n"
    "                """)\n"
    "                row = await cursor.fetchone()\n"
    "                cursor2 = await conn.execute("""\n"
    "                    SELECT model, COUNT(*) AS c, SUM(cost_usd) AS cost_sum\n"
    "                    FROM ai_usage WHERE DATE(created_at) = DATE("now")\n"
    "                    GROUP BY model ORDER BY c DESC\n"
    "                """)\n"
)
if old in r:
    r = r.replace(old, new)
    open("src/agents/ai_router.py","w",encoding="utf-8").write(r)
    print("FIX 1: Applied")
else:
    print("FIX 1: Pattern mismatch")
    print("OLD repr:", repr(old[:80]))
