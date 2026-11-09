import asyncio, pytest
from bridge import run_script

READS = {"telegram.get_history"}
async def fake_call(name, args):
    return [{"text": f"msg in {args['chat_id']}"}]

def run(script):
    return asyncio.run(run_script(script, fake_call, lambda n: n in READS, timeout=20))

def test_read_chain():
    out = run("const h = await telegram.get_history({chat_id: 5}); return h.map(m => m.text);")
    assert out == ["msg in 5"]

def test_mutation_refused():
    with pytest.raises(RuntimeError, match="mutation not allowed"):
        run("return await telegram.send_message({text:'x'});")

def test_naive_escape_paths_closed():
    out = run("""
      let dyn = 'blocked';
      try { await import('node:fs'); dyn = 'open'; } catch (e) {}
      return { fetch: typeof fetch, process: typeof process, require: typeof require, dyn };
    """)
    assert out == {"fetch": "undefined", "process": "undefined", "require": "undefined", "dyn": "blocked"}
