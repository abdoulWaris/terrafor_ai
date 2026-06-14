"""tfai - CLI pour générer et appliquer du Terraform via un LLM (Ollama) + LocalStack.

Exemples :
    tfai init
    tfai ask "crée un bucket S3 nommé uploads avec versioning activé"
    tfai plan
    tfai apply -y
    tfai chat
"""
from __future__ import annotations

import difflib
import os
import sys
from pathlib import Path

import click

from . import ollama_client
from . import terraform_manager as tfm
from .prompts import SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = os.environ.get("TFAI_MODEL", "llama3.1")
DEFAULT_DIR = os.environ.get("TFAI_DIR", "terraform")
MAIN_TF = "main.tf"


def _read_main_tf(tf_dir: Path) -> str:
    path = tf_dir / MAIN_TF
    return path.read_text() if path.exists() else ""


def _write_main_tf(tf_dir: Path, content: str) -> None:
    (tf_dir / MAIN_TF).write_text(content)


def _print_diff(old: str, new: str) -> None:
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="main.tf (avant)",
        tofile="main.tf (après)",
    )
    diff_text = "".join(diff)
    click.echo(diff_text if diff_text.strip() else "(aucun changement)")


@click.group()
@click.option(
    "--dir", "tf_dir", default=DEFAULT_DIR, show_default=True,
    help="Répertoire du projet Terraform géré par tfai.",
)
@click.option(
    "--model", default=DEFAULT_MODEL, show_default=True,
    help="Modèle Ollama à utiliser (variable d'env TFAI_MODEL).",
)
@click.pass_context
def main(ctx: click.Context, tf_dir: str, model: str) -> None:
    """tfai : pilote Terraform + LocalStack en langage naturel via Ollama."""
    ctx.ensure_object(dict)
    ctx.obj["dir"] = Path(tf_dir)
    ctx.obj["model"] = model


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialise le répertoire Terraform (provider.tf + terraform init)."""
    tf_dir: Path = ctx.obj["dir"]
    tf_dir.mkdir(parents=True, exist_ok=True)

    provider_path = tf_dir / "provider.tf"
    if not provider_path.exists():
        template = Path(__file__).parent / "templates" / "provider.tf"
        provider_path.write_text(template.read_text())
        click.echo(f"[tfai] Créé {provider_path}")

    main_tf = tf_dir / MAIN_TF
    if not main_tf.exists():
        main_tf.write_text(
            "# Géré par tfai\n"
            "# Ce fichier est généré/modifié automatiquement via `tfai ask` / `tfai chat`.\n"
        )
        click.echo(f"[tfai] Créé {main_tf}")

    result = tfm.run_terraform(["init"], cwd=tf_dir)
    click.echo(result.stdout)
    if result.returncode != 0:
        click.echo(result.stderr, err=True)
        sys.exit(result.returncode)


@main.command()
@click.argument("instruction", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Applique les changements sans confirmation.")
@click.option("--no-validate", is_flag=True, help="Ne lance pas `terraform validate` après écriture.")
@click.pass_context
def ask(ctx: click.Context, instruction: tuple[str, ...], yes: bool, no_validate: bool) -> None:
    """Demande au LLM de générer/modifier les ressources Terraform."""
    tf_dir: Path = ctx.obj["dir"]
    model: str = ctx.obj["model"]
    instruction_text = " ".join(instruction)

    if not (tf_dir / "provider.tf").exists():
        click.echo("[tfai] Répertoire non initialisé. Lancez d'abord `tfai init`.", err=True)
        sys.exit(1)

    current_tf = _read_main_tf(tf_dir)
    user_prompt = build_user_prompt(instruction_text, current_tf)

    click.echo(f"[tfai] Interrogation du modèle '{model}'…")
    try:
        response = ollama_client.chat(
            model=model,
            messages=[{"role": "user", "content": user_prompt}],
            system=SYSTEM_PROMPT,
        )
    except Exception as exc:  # connexion Ollama, modèle absent, etc.
        click.echo(f"[tfai] Erreur lors de l'appel à Ollama : {exc}", err=True)
        click.echo("[tfai] Vérifiez que `ollama serve` tourne et que le modèle est bien pull (ollama pull <modèle>).", err=True)
        sys.exit(1)

    new_blocks = tfm.extract_hcl_code(response)
    if not new_blocks.strip():
        click.echo("[tfai] Le modèle n'a renvoyé aucun bloc HCL exploitable.")
        click.echo("--- Réponse brute ---")
        click.echo(response)
        return

    merged = tfm.merge_hcl(current_tf, new_blocks)

    click.echo("\n--- Diff proposé sur main.tf ---")
    _print_diff(current_tf, merged)

    if not yes and not click.confirm("\nAppliquer ces changements à main.tf ?", default=True):
        click.echo("[tfai] Abandon, main.tf inchangé.")
        return

    _write_main_tf(tf_dir, merged)

    fmt_result = tfm.run_terraform(["fmt"], cwd=tf_dir)
    if fmt_result.returncode != 0:
        click.echo(fmt_result.stderr, err=True)

    if not no_validate:
        val = tfm.run_terraform(["validate"], cwd=tf_dir)
        if val.returncode != 0:
            click.echo(val.stdout)
            click.echo(val.stderr, err=True)
            click.echo("[tfai] ⚠️  Le fichier généré n'est pas valide. main.tf a été écrit, à corriger/relancer.")
            return

    click.echo(f"[tfai] ✅ {MAIN_TF} mis à jour et validé.")
    click.echo("[tfai] Lancez `tfai plan` pour voir l'impact sur LocalStack.")


@main.command()
@click.pass_context
def plan(ctx: click.Context) -> None:
    """Lance `terraform plan` (contre LocalStack via provider.tf)."""
    tf_dir: Path = ctx.obj["dir"]
    result = tfm.run_terraform(["plan"], cwd=tf_dir)
    click.echo(result.stdout)
    if result.returncode != 0:
        click.echo(result.stderr, err=True)
        sys.exit(result.returncode)


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Equivalent de -auto-approve.")
@click.pass_context
def apply(ctx: click.Context, yes: bool) -> None:
    """Lance `terraform apply` contre LocalStack."""
    tf_dir: Path = ctx.obj["dir"]
    args = ["apply"]
    if yes:
        args.append("-auto-approve")
    result = tfm.run_terraform(args, cwd=tf_dir)
    click.echo(result.stdout)
    if result.returncode != 0:
        click.echo(result.stderr, err=True)
        sys.exit(result.returncode)


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Equivalent de -auto-approve.")
@click.pass_context
def destroy(ctx: click.Context, yes: bool) -> None:
    """Lance `terraform destroy` contre LocalStack."""
    tf_dir: Path = ctx.obj["dir"]
    args = ["destroy"]
    if yes:
        args.append("-auto-approve")
    result = tfm.run_terraform(args, cwd=tf_dir)
    click.echo(result.stdout)
    if result.returncode != 0:
        click.echo(result.stderr, err=True)
        sys.exit(result.returncode)


@main.command()
@click.pass_context
def show(ctx: click.Context) -> None:
    """Affiche le contenu actuel de main.tf."""
    tf_dir: Path = ctx.obj["dir"]
    click.echo(_read_main_tf(tf_dir) or "(vide)")


@main.command(name="models")
def models() -> None:
    """Liste les modèles Ollama disponibles localement."""
    try:
        for name in ollama_client.list_models():
            click.echo(name)
    except Exception as exc:
        click.echo(f"[tfai] Erreur lors de la connexion à Ollama : {exc}", err=True)
        sys.exit(1)


@main.command()
@click.pass_context
def chat(ctx: click.Context) -> None:
    """Mode interactif : enchaîne des instructions en langage naturel."""
    click.echo("Mode chat tfai. Tapez 'exit' pour quitter, 'plan' / 'apply' / 'show' pour les commandes correspondantes.\n")
    while True:
        instruction = click.prompt(">", prompt_suffix=" ")
        text = instruction.strip()
        low = text.lower()
        if low in {"exit", "quit"}:
            break
        if low == "plan":
            ctx.invoke(plan)
            continue
        if low == "apply":
            ctx.invoke(apply, yes=False)
            continue
        if low == "show":
            ctx.invoke(show)
            continue
        if not text:
            continue
        ctx.invoke(ask, instruction=(text,), yes=False, no_validate=False)


if __name__ == "__main__":
    main()
