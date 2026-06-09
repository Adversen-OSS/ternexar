#!/usr/bin/env python3
import subprocess
from pathlib import Path

ROOT = Path.cwd()

def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=15)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)

def check(name, ok, detail=""):
    print(("✅" if ok else "❌") + " " + name)
    if detail:
        print("   " + detail)

print("\nTERNEXAR AutoFix Engine v1 — Preflight Check\n")

check("Project folder", (ROOT / "pyproject.toml").exists(), str(ROOT))

code, out, err = run("git status --short")
check("Git clean", code == 0 and out == "", out or err or "working tree clean")

code, out, err = run("git branch --show-current")
check("Branch", code == 0 and bool(out), out or err)

code, out, err = run("git remote -v")
check("GitHub remote", "github.com" in out, out or err)

code, out, err = run("python3 --version")
check("Python", code == 0, out or err)

check("README exists", (ROOT / "README.md").exists())
check("src exists", (ROOT / "src").exists())
check("tests exists", (ROOT / "tests").exists())

print("\nNext:")
print("git status")
print("git add scripts/ternexar_preflight.py")
print("git commit -m 'Add TERNEXAR AutoFix preflight'")
print("git push")
