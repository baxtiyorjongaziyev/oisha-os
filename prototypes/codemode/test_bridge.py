import asyncio, pytest
from bridge import run_script

READS = {"telegram.get_history"}
async def fake_call(name, args):
    return [{"text": f"msg in {args['chat_id']}"}]

def run(script):
    return asyncio.run(run_script(script, fake_call, lambda n: n in READS, timeout=20, sandbox='node', allow_unsafe_node=True))

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


def test_input_validation_and_docker_command():
    from pathlib import Path
    from bridge import build_command, validate_inputs
    with pytest.raises(ValueError, match="development-only"):
        validate_inputs("node", ("telegram",), False)
    with pytest.raises(ValueError, match="unsupported"):
        validate_inputs("bash", ("telegram",), True)
    for bad in (("../x",), ("telegram;rm",), ("evil",), ()):
        with pytest.raises(ValueError, match="namespaces"):
            validate_inputs("docker", bad, False)
    cmd = build_command("docker", Path("/tmp/x/script.js"), "telegram,amo")
    for flag in ("--network", "none", "--read-only", "--cap-drop", "ALL", "no-new-privileges", "65534:65534"):
        assert flag in cmd
    assert cmd[cmd.index("--network") + 1] == "none" and cmd[-1] == "/work"


def test_symlink_script_rejected(tmp_path):
    import subprocess, shutil
    from bridge import RUNNER
    real = tmp_path / "real.js"
    real.write_text("return 1")
    link = tmp_path / "script.js"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks unavailable")
    r = subprocess.run([shutil.which("node"), str(RUNNER), str(link), "telegram", str(tmp_path)],
                       capture_output=True, timeout=20)
    assert r.returncode != 0 and b"outside managed directory" in r.stderr
