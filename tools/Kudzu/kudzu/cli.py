"""kudzu command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from kudzu import __version__
from kudzu.config import PASSWORD_LIST_ENC_PATH, PASSWORD_LIST_PATH, load_config
from kudzu.exporters import write_wordlist
from kudzu.rules import generate_variants
from kudzu.storage import GpgNotAvailable, PasswordStore

app = typer.Typer(
    name="kudzu",
    help=(
        "Wordlist generator for pentest password spraying, built from "
        "passwords found during an audit.\n\n"
        "Accumulate passwords found during an engagement (internal, external, "
        "web, cloud...), then grow them into a focused candidate list instead "
        "of reinventing a rule engine every time."
    ),
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kudzu {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show kudzu's version and exit.",
    ),
) -> None:
    pass


def _get_store(verbose: bool = False) -> PasswordStore:
    config = load_config()
    try:
        return PasswordStore(encryption=config["storage"]["encryption"], verbose=verbose)
    except GpgNotAvailable as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


@app.command()
def add(
    password: str = typer.Argument(..., help="The password to store."),
    tag: str = typer.Option("", "--tag", help="Context tag, e.g. smb, ldap, kerberoast, mail."),
    rules: bool = typer.Option(
        False, "--rules",
        help=(
            "Apply mutation rules to this password in create-list. Without "
            "this flag the password is stored and still included as-is in "
            "the generated wordlist, but no mutations are built around it "
            "(useful for high-entropy / randomly generated credentials)."
        ),
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
) -> None:
    """Add a discovered password to the local store."""
    store = _get_store(verbose=verbose)
    added = store.add(password, tag=tag, apply_rules=rules)
    if added:
        typer.secho(
            f"Added password (tag={tag or '-'}, rules={'on' if rules else 'off'}).",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho("Already in store, skipped.", fg=typer.colors.YELLOW)


@app.command("create-list")
def create_list(
    output_path: Path = typer.Argument(..., help="Where to write the generated wordlist."),
    keyword: Optional[str] = typer.Option(
        None, "--keyword",
        help="Extra word to combine into tested passwords (company name, target name, project codename...).",
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose"),
) -> None:
    """Generate a mutated wordlist from every stored password.

    Passwords added with --rules are expanded through the mutation engine;
    passwords added without it are included as-is, unmutated.
    """
    config = load_config()
    store = _get_store(verbose=verbose)
    entries = store.load()
    if not entries:
        typer.secho("No passwords stored yet. Use `kudzu add <password>` first.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    all_variants: set[str] = set()
    for entry in entries:
        if entry.apply_rules:
            variants = generate_variants(entry.password, config, keyword=keyword)
            if verbose:
                typer.echo(f"[kudzu] {entry.password} -> {len(variants)} variants", err=True)
            all_variants |= set(variants)
        else:
            if verbose:
                typer.echo(f"[kudzu] {entry.password} -> kept as-is (no --rules)", err=True)
            all_variants.add(entry.password)

    ordered = sorted(all_variants, key=lambda s: (len(s), s))
    count = write_wordlist(ordered, output_path)
    typer.secho(
        f"Wrote {count} candidate passwords to {output_path} "
        f"(from {len(entries)} stored seed passwords).",
        fg=typer.colors.GREEN,
    )


@app.command("list")
def list_passwords() -> None:
    """Show all stored passwords with their tags, timestamps and rules flag."""
    store = _get_store()
    entries = store.load()
    if not entries:
        typer.echo("No passwords stored.")
        return
    for e in entries:
        tag = e.tag or "-"
        ts = e.timestamp or "-"
        rules = "rules=on" if e.apply_rules else "rules=off"
        typer.echo(f"{e.password}\ttag={tag}\tadded={ts}\t{rules}")


@app.command()
def remove(
    password: Optional[str] = typer.Option(None, "--password", help="Remove the entry matching this exact password."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Remove every entry matching this tag."),
) -> None:
    """Remove stored password(s), either by exact password or by tag."""
    if password and tag:
        typer.secho("Pass either --password or --tag, not both.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if not password and not tag:
        typer.secho("Pass --password <value> or --tag <value>.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    store = _get_store()
    if password:
        if store.remove_by_password(password):
            typer.secho("Removed.", fg=typer.colors.GREEN)
        else:
            typer.secho("Not found in store.", fg=typer.colors.YELLOW)
    else:
        count = store.remove_by_tag(tag)
        if count:
            typer.secho(f"Removed {count} entr{'y' if count == 1 else 'ies'} tagged '{tag}'.", fg=typer.colors.GREEN)
        else:
            typer.secho(f"No entries found with tag '{tag}'.", fg=typer.colors.YELLOW)


@app.command()
def clear(
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Wipe the entire password store."""
    if not yes:
        confirm = typer.confirm("This will permanently delete all stored passwords. Continue?")
        if not confirm:
            raise typer.Abort()
    store = _get_store()
    count = store.clear()
    typer.secho(f"Cleared {count} stored passwords.", fg=typer.colors.GREEN)


@app.command("import")
def import_passwords(
    file: Path = typer.Argument(..., help="File with one password per line (e.g. secretsdump/Hashcat output)."),
    tag: str = typer.Option("", "--tag", help="Tag applied to every imported password."),
    rules: bool = typer.Option(
        False, "--rules", help="Apply mutation rules to every imported password in create-list."
    ),
) -> None:
    """Bulk-import passwords from an existing file."""
    if not file.exists():
        typer.secho(f"File not found: {file}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    store = _get_store()
    added, skipped = store.import_file(file, tag=tag, apply_rules=rules)
    typer.secho(f"Imported {added} new password(s), skipped {skipped} duplicate(s).", fg=typer.colors.GREEN)


@app.command()
def where() -> None:
    """Print the on-disk storage/config locations kudzu is using."""
    config = load_config()
    typer.echo(f"config:   {PASSWORD_LIST_PATH.parent.parent / 'config.yaml'}")
    if config["storage"]["encryption"] == "gpg":
        typer.echo(f"store:    {PASSWORD_LIST_ENC_PATH} (gpg-encrypted)")
    else:
        typer.echo(f"store:    {PASSWORD_LIST_PATH}")


if __name__ == "__main__":
    app()
