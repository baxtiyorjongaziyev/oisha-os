import sys
sys.stdout = open("fix_log.txt","w",encoding="utf-8")
print("=== FIXES START ===")
print()
# FIX 1 - read file
with open("src/agents/ai_router.py",encoding="utf-8") as f:
    content = f.read()
lines = content.split("\n")
print("Line count:", len(lines))
old = "\n".join(lines[516:538])
print("Old block found:", old in content)
if old in content:
    new_parts = []
    new_parts.append("            if date:")
    new_parts.append("                cursor = await conn.execute(""""""")
    new_parts.append("                    SELECT")
    new_parts.append("                      COUNT(*) AS calls,")
    new_parts.append("                      SUM(tokens_in) AS tok_in,")
    new_parts.append("                      SUM(tokens_out) AS tok_out,")
    new_parts.append("                      SUM(cost_usd) AS cost,")
    new_parts.append("                      AVG(latency_ms) AS lat,")
    new_parts.append("                      SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) AS ok,")
    new_parts.append("                      SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) AS fail")
