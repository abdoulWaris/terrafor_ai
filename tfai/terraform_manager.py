"""Utilitaires pour manipuler le HCL généré et piloter le binaire `terraform`."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Repère l'en-tête d'un bloc top-level : resource "type" "name" {  /  variable "x" {  / etc.
_HEADER_RE = re.compile(r'^\s*(resource|data|variable|output)\s+((?:"[^"]*"\s*)+)\{')


def extract_hcl_code(llm_response: str) -> str:
    """Extrait le contenu d'un bloc ```hcl ... ``` (ou ```terraform ... ```).

    Si aucun bloc de code n'est trouvé, retourne la réponse brute (au cas où
    le modèle aurait renvoyé du HCL sans le délimiter).
    """
    match = re.search(r"```(?:hcl|terraform)?\s*\n(.*?)```", llm_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_response.strip()


def parse_blocks(content: str) -> list[tuple[str, str]]:
    """Découpe un contenu HCL en blocs top-level (resource/data/variable/output).

    Retourne une liste de tuples (clé, texte_du_bloc) où la clé identifie le
    bloc de façon unique, par ex. `resource.aws_s3_bucket.uploads`.
    Le texte hors de tout bloc top-level (commentaires, lignes vides en tête
    de fichier...) est ignoré par cette fonction.
    """
    blocks: list[tuple[str, str]] = []
    lines = content.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _HEADER_RE.match(line)
        if not m:
            i += 1
            continue

        kind = m.group(1)
        idents = re.findall(r'"([^"]*)"', m.group(2))
        key = ".".join([kind, *idents])

        depth = line.count("{") - line.count("}")
        block_lines = [line]
        i += 1
        while depth > 0 and i < len(lines):
            block_lines.append(lines[i])
            depth += lines[i].count("{") - lines[i].count("}")
            i += 1

        blocks.append((key, "".join(block_lines)))

    return blocks


def merge_hcl(existing: str, new_content: str) -> str:
    """Fusionne `new_content` (généré par le LLM) dans `existing`.

    Les blocs ayant la même clé (type + nom(s)) sont remplacés ; les nouveaux
    sont ajoutés à la fin. L'en-tête (commentaires en début de fichier) du
    fichier existant est conservé.
    """
    existing_blocks = parse_blocks(existing)
    new_blocks = parse_blocks(new_content)

    # Conserve l'en-tête (tout ce qui précède le premier bloc top-level)
    if existing_blocks:
        first_block_text = existing_blocks[0][1]
        header_end = existing.find(first_block_text)
        header = existing[:header_end]
    else:
        header = existing if existing.strip() else ""

    merged: dict[str, str] = {key: text for key, text in existing_blocks}
    order: list[str] = [key for key, _ in existing_blocks]

    for key, block in new_blocks:
        if key not in merged:
            order.append(key)
        merged[key] = block

    body = "\n".join(merged[k].rstrip() + "\n" for k in order)

    if header and not header.endswith("\n\n"):
        header = header.rstrip("\n") + "\n\n"

    return header + body


def run_terraform(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Exécute `terraform <args>` dans `cwd` et retourne le résultat."""
    return subprocess.run(
        ["terraform", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
    )
