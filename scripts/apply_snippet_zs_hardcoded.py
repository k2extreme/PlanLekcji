#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import os
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
LISTA = ROOT / "lista.html"
SNIPPET = ROOT / "snippet-ZS.txt"

# ===== HARDKODOWANE FRAGMENTY (źródło prawdy) =====

STYLE_BLOCK_LINES = [
    "<style>",
    "\t        /* Styl dla centrowania i dodania odstępu tekstu pod obrazem */",
    "\t        .logo-container {",
    "\t            text-align: center;",
    "\t            padding-bottom: 10px;",
    "\t            width: 99%;",
    "\t        }",
    "\t        .logo-container a {",
    "\t            display: inline-block;",
    "\t            text-align: center;",
    "\t            color: #000;",
    "\t            text-decoration: none;",
    "\t        }",
    "\t        .logo-container img {",
    "\t            display: block;",
    "\t            margin: 0 auto;",
    "\t            width: 60px;",
    "\t            height: 60px;",
    "\t        }",
    "\t        .logo-container .logo-text {",
    "\t            display: block;",
    "\t            margin-top: 5px;",
    "\t            font-size: 14px;",
    "\t        }",
    "</style>",
]

LOGO_BLOCK_LINES = [
    "  <!-- Wycentrowany hyperlink z logo i tekstem pod obrazem -->",
    "    <tr>",
    '\t        <td class="logo-container" colspan="2">',
    '\t            <a href="https://zsszubin.edupage.org/" target="_top">',
    '\t                <img src="//cloud9.edupage.org/cloud?z%3AApgp8e0q%2FdMflhPxiJwxw7ANQ4DnotmxDWb4iMWbUWzE92DWMca1qlChHEpYs25jUpqkSWBiHLjhOo4ZJe%2FqG8OA372M0lqCP9Mc6d1a7S8%3D" alt="Strona domowa ZS Szubin">',
    "\t                <span class=\"logo-text\">Strona domowa<br>ZS Szubin</span>",
    "\t            </a>",
    "\t        </td>",
    "\t    </tr>",
]

# Markery idempotencji
STYLE_MARKER = ".logo-container"
LOGO_MARKER = 'class="logo-container"'


def detect_newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def normalize_block(lines: list[str]) -> str:
    # porównywanie odporne na końcowe spacje i nadmiar pustych linii na brzegach
    norm = [ln.rstrip() for ln in lines]
    while norm and norm[0] == "":
        norm.pop(0)
    while norm and norm[-1] == "":
        norm.pop()
    return "\n".join(norm)


def read_text(path: Path) -> tuple[str, str, bool]:
    raw = path.read_text(encoding="utf-8", errors="strict")
    nl = detect_newline(raw)
    ends_nl = raw.endswith("\n")
    text = raw.replace("\r\n", "\n")
    return text, nl, ends_nl


def write_text(path: Path, text_unix: str, nl: str, ends_nl: bool) -> None:
    out = text_unix.replace("\n", nl)
    if ends_nl and not out.endswith(nl):
        out += nl
    path.write_text(out, encoding="utf-8")


def extract_from_snippet(snippet_unix: str) -> tuple[list[str], list[str]]:
    lines = snippet_unix.split("\n")

    # Kotwice wg snippet-ZS.txt: link -> script
    def find_exact(needle: str) -> int:
        for i, ln in enumerate(lines):
            if ln.strip() == needle:
                return i
        raise ValueError(f"snippet-ZS: nie znaleziono kotwicy: {needle}")

    A1 = '<link rel="stylesheet" href="css/lista.css" type="text/css">'
    A2 = '<script language="JavaScript1.2" type="text/javascript">'
    B1 = '<table border="0" cellpadding="2" cellspacing="0">'
    B2 = "<tr><td>"

    i_a1 = find_exact(A1)
    i_a2 = find_exact(A2)
    style_lines = lines[i_a1 + 1 : i_a2]  # bez kotwic

    i_b1 = find_exact(B1)
    i_b2 = find_exact(B2)
    logo_lines = lines[i_b1 + 1 : i_b2]   # bez kotwic

    # usuń puste ogony
    while style_lines and style_lines[-1] == "":
        style_lines.pop()
    while logo_lines and logo_lines[-1] == "":
        logo_lines.pop()

    return style_lines, logo_lines


def validate_snippet_contract() -> None:
    if not SNIPPET.exists():
        return

    snippet_unix, _, _ = read_text(SNIPPET)
    s_style, s_logo = extract_from_snippet(snippet_unix)

    want_style = normalize_block(STYLE_BLOCK_LINES)
    want_logo = normalize_block(LOGO_BLOCK_LINES)
    got_style = normalize_block(s_style)
    got_logo = normalize_block(s_logo)

    if got_style != want_style or got_logo != want_logo:
        print("[warn] snippet-ZS.txt różni się od hardkodu (walidacja informacyjna).")
        # jeśli chcesz tryb twardy, to dopiero wtedy:
        if os.getenv("STRICT_SNIPPET_CONTRACT") == "1":
            raise ValueError("snippet-ZS.txt NIE jest zgodny z hardkodem w skrypcie.")



def find_line_idx(lines: list[str], predicate) -> int:
    for i, ln in enumerate(lines):
        if predicate(ln):
            return i
    return -1


def patch_style(lines: list[str]) -> tuple[list[str], bool]:
    # 1) jeśli istnieje <style>..</style> zawierający .logo-container -> replace (lub no-op)
    i = 0
    while i < len(lines):
        if lines[i].strip() == "<style>":
            j = i + 1
            while j < len(lines) and lines[j].strip() != "</style>":
                j += 1
            if j < len(lines):  # mamy blok
                block = lines[i : j + 1]
                if any(STYLE_MARKER in ln for ln in block):
                    if normalize_block(block) == normalize_block(STYLE_BLOCK_LINES):
                        return lines, False
                    # replace
                    new_lines = lines[:i] + STYLE_BLOCK_LINES + lines[j + 1 :]
                    return new_lines, True
            i = j + 1
        else:
            i += 1

    # 2) brak bloku -> insert po <link ... css/lista.css ...>
    idx = find_line_idx(
        lines,
        lambda ln: "<link" in ln and "href=\"css/lista.css\"" in ln and "rel=\"stylesheet\"" in ln,
    )
    if idx == -1:
        # fallback: regex na wypadek drobnych zmian atrybutów
        link_re = re.compile(r"<link\b[^>]*\bhref=[\"']css/lista\.css[\"'][^>]*>", re.IGNORECASE)
        idx = find_line_idx(lines, lambda ln: bool(link_re.search(ln)))
    if idx == -1:
        raise ValueError("lista.html: nie znaleziono <link ... css/lista.css ...> (nie wiem gdzie wstawić <style>)")

    new_lines = lines[: idx + 1] + STYLE_BLOCK_LINES + lines[idx + 1 :]
    return new_lines, True


def patch_logo(lines: list[str]) -> tuple[list[str], bool]:
    # jeśli istnieje logo-container -> replace całego wiersza logo (z komentarzem, jeśli jest)
    idx_logo = find_line_idx(lines, lambda ln: LOGO_MARKER in ln)
    if idx_logo != -1:
        # szukaj początku <tr> w górę
        i = idx_logo
        while i >= 0 and "<tr" not in lines[i]:
            i -= 1
        if i < 0:
            i = idx_logo

        # jeśli linia nad <tr> to komentarz o “Wycentrowany hyperlink ...” -> włącz ją
        if i - 1 >= 0 and "Wycentrowany hyperlink z logo i tekstem pod obrazem" in lines[i - 1]:
            i -= 1

        # szukaj końca </tr> w dół (pierwsze domknięcie po logo)
        j = idx_logo
        while j < len(lines) and "</tr>" not in lines[j]:
            j += 1
        if j >= len(lines):
            raise ValueError("lista.html: znaleziono logo-container, ale nie znaleziono domknięcia </tr>")

        current = lines[i : j + 1]
        if normalize_block(current) == normalize_block(LOGO_BLOCK_LINES):
            return lines, False

        new_lines = lines[:i] + LOGO_BLOCK_LINES + lines[j + 1 :]
        return new_lines, True

    # brak logo -> insert po <table border="0" cellpadding="2" cellspacing="0">
    idx_table = find_line_idx(lines, lambda ln: ln.strip() == '<table border="0" cellpadding="2" cellspacing="0">')
    if idx_table == -1:
        # fallback regex
        table_re = re.compile(r"<table\b[^>]*\bborder=[\"']0[\"'][^>]*>", re.IGNORECASE)
        idx_table = find_line_idx(lines, lambda ln: bool(table_re.search(ln)))
    if idx_table == -1:
        raise ValueError("lista.html: nie znaleziono <table ...> (nie wiem gdzie wstawić wiersz logo)")

    new_lines = lines[: idx_table + 1] + LOGO_BLOCK_LINES + lines[idx_table + 1 :]
    return new_lines, True


def main() -> int:
    validate_snippet_contract()

    if not LISTA.exists():
        print("[skip] Brak lista.html")
        return 0

    lista_unix, nl, ends_nl = read_text(LISTA)
    lines = lista_unix.split("\n")

    changed = False

    lines, ch1 = patch_style(lines)
    changed |= ch1

    lines, ch2 = patch_logo(lines)
    changed |= ch2

    if not changed:
        print("[ok] Brak zmian – lista.html już zgodna.")
        return 0

    out_unix = "\n".join(lines)
    write_text(LISTA, out_unix, nl, ends_nl)
    print("[done] Zapisano zmodyfikowany lista.html")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"[error] {e}", file=sys.stderr)
        raise
