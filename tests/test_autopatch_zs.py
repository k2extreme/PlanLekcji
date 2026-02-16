from __future__ import annotations
from pathlib import Path
import subprocess
import shutil
import os

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply_snippet_zs_hardcoded.py"

STYLE_MARKER = ".logo-container"
LOGO_MARKER = 'class="logo-container"'


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def write(p: Path, txt: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(txt, encoding="utf-8")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def make_repo_copy(tmp_path: Path) -> Path:
    # Kopia robocza repo do izolacji testów (bez ruszania prawdziwego pliku lista.html)
    work = tmp_path / "work"
    shutil.copytree(ROOT, work, dirs_exist_ok=True)
    return work


def test_idempotent(tmp_path: Path) -> None:
    work = make_repo_copy(tmp_path)

    # 1st run
    r1 = run(["python", str(SCRIPT)], cwd=work)
    assert r1.returncode == 0, r1.stderr

    first = read(work / "lista.html")

    # 2nd run
    r2 = run(["python", str(SCRIPT)], cwd=work)
    assert r2.returncode == 0, r2.stderr

    second = read(work / "lista.html")
    assert first == second, "Drugi run zmienił plik (brak idempotencji)"


def test_contains_markers(tmp_path: Path) -> None:
    work = make_repo_copy(tmp_path)

    r = run(["python", str(SCRIPT)], cwd=work)
    assert r.returncode == 0, r.stderr

    out = read(work / "lista.html")
    assert STYLE_MARKER in out
    assert LOGO_MARKER in out

    # Obiektywnie: marker ma wystąpić raz (nie duplikujemy)
    assert out.count(STYLE_MARKER) >= 1
    assert out.count(LOGO_MARKER) == 1


def test_replace_if_present_but_different(tmp_path: Path) -> None:
    work = make_repo_copy(tmp_path)
    lista = work / "lista.html"

    # Wymuś „zły” styl i „złe” logo, ale z markerami – skrypt ma to podmienić.
    bad = read(lista).replace(
        "<style>",
        "<style>\n.logo-container{width:1px;}\n"
    ).replace(
        LOGO_MARKER,
        'class="logo-container" data-bad="1"'
    )
    write(lista, bad)

    r = run(["python", str(SCRIPT)], cwd=work)
    assert r.returncode == 0, r.stderr

    out = read(lista)
    assert 'data-bad="1"' not in out, "Nie podmieniło wiersza logo"
    assert "width:1px" not in out, "Nie podmieniło stylu"


def test_fail_when_anchor_missing(tmp_path: Path) -> None:
    work = make_repo_copy(tmp_path)
    lista = work / "lista.html"

    # Usuń kotwicę linka do lista.css => skrypt ma failować
    out = read(lista).replace('href="css/lista.css"', 'href="css/NOPE.css"')
    write(lista, out)

    r = run(["python", str(SCRIPT)], cwd=work)
    assert r.returncode != 0
    assert "nie znaleziono" in (r.stderr + r.stdout).lower()


def test_contract_snippet_mismatch_fails(tmp_path: Path) -> None:
    work = make_repo_copy(tmp_path)
    snippet = work / "snippet-ZS.txt"

    # Zmień snippet minimalnie => ma failować na walidacji
    write(snippet, read(snippet).replace(".logo-container", ".logo-containerXXX"))

    r = run(["python", str(SCRIPT)], cwd=work)
    assert r.returncode != 0
    assert "nie jest zgodny" in (r.stderr + r.stdout).lower()


def test_contract_mismatch_can_warn(tmp_path: Path) -> None:
    work = make_repo_copy(tmp_path)
    snippet = work / "snippet-ZS.txt"
    write(snippet, read(snippet).replace(".logo-container", ".logo-containerXXX"))

    env = os.environ.copy()
    env["ALLOW_SNIPPET_MISMATCH"] = "1"

    r = subprocess.run(
        ["python", str(SCRIPT)],
        cwd=work,
        text=True,
        capture_output=True,
        env=env,
    )
    assert r.returncode == 0
    assert "[warn]" in (r.stdout + r.stderr)
