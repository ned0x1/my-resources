"""Local password storage for kudzu.

Storage format (~/.kudzu/password/list.txt): one entry per line,
tab-separated:

    <password>\t<tag>\t<iso8601-timestamp>\t<apply_rules: 0|1>

`tag` and `timestamp` may be empty strings. `apply_rules` records whether
this password was added with `--rules`: only passwords added that way get
mutated by `create-list`. Passwords added without `--rules` (the default)
are kept in the store and still end up in the generated wordlist as-is,
but no mutation rules are applied around them — useful for high-entropy /
randomly generated credentials where mutating them is pointless. Passwords
containing a literal tab character are not supported (extremely rare in
practice for pentest creds).

If storage.encryption is set to "gpg" in config.yaml, the file is kept on
disk as list.txt.gpg (GPG symmetric encryption) and transparently
decrypted/re-encrypted in memory on each operation. This requires the
system `gpg` binary to be available on PATH.
"""

from __future__ import annotations

import getpass
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kudzu.config import PASSWORD_LIST_ENC_PATH, PASSWORD_LIST_PATH, ensure_kudzu_home


@dataclass
class Entry:
    password: str
    tag: str = ""
    timestamp: str = ""
    apply_rules: bool = False

    def to_line(self) -> str:
        return f"{self.password}\t{self.tag}\t{self.timestamp}\t{int(self.apply_rules)}"

    @staticmethod
    def from_line(line: str) -> "Entry":
        parts = line.rstrip("\n").split("\t")
        password = parts[0] if len(parts) > 0 else ""
        tag = parts[1] if len(parts) > 1 else ""
        timestamp = parts[2] if len(parts) > 2 else ""
        # Older stores (pre --rules) won't have a 4th column; default to False.
        apply_rules = parts[3] == "1" if len(parts) > 3 else False
        return Entry(password=password, tag=tag, timestamp=timestamp, apply_rules=apply_rules)


class GpgNotAvailable(RuntimeError):
    pass


class PasswordStore:
    def __init__(self, encryption: str = "none", verbose: bool = False):
        self.encryption = encryption
        self.verbose = verbose
        ensure_kudzu_home()
        if self.encryption == "gpg" and shutil.which("gpg") is None:
            raise GpgNotAvailable(
                "storage.encryption is set to 'gpg' in config.yaml but the "
                "`gpg` binary was not found on PATH. Install GnuPG or set "
                "storage.encryption back to 'none'."
            )

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"[kudzu] {msg}", file=sys.stderr)

    # -- raw read/write -----------------------------------------------

    def _read_raw(self) -> str:
        if self.encryption == "gpg":
            if not PASSWORD_LIST_ENC_PATH.exists():
                return ""
            passphrase = getpass.getpass("GPG passphrase for kudzu store: ")
            result = subprocess.run(
                [
                    "gpg", "--quiet", "--batch", "--yes",
                    "--passphrase-fd", "0",
                    "--decrypt", str(PASSWORD_LIST_ENC_PATH),
                ],
                input=passphrase.encode() + b"\n",
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"gpg decryption failed: {result.stderr.decode(errors='replace')}"
                )
            return result.stdout.decode()
        else:
            if not PASSWORD_LIST_PATH.exists():
                return ""
            return PASSWORD_LIST_PATH.read_text(encoding="utf-8")

    def _write_raw(self, content: str) -> None:
        if self.encryption == "gpg":
            passphrase = getpass.getpass("GPG passphrase for kudzu store: ")
            confirm = getpass.getpass("Confirm passphrase: ")
            if passphrase != confirm:
                raise RuntimeError("Passphrases did not match, aborting write.")
            result = subprocess.run(
                [
                    "gpg", "--quiet", "--batch", "--yes",
                    "--symmetric", "--cipher-algo", "AES256",
                    "--passphrase-fd", "0",
                    "--output", str(PASSWORD_LIST_ENC_PATH),
                ],
                input=passphrase.encode() + b"\n" + content.encode(),
                capture_output=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"gpg encryption failed: {result.stderr.decode(errors='replace')}"
                )
            # Never leave a plaintext copy lying around.
            if PASSWORD_LIST_PATH.exists():
                PASSWORD_LIST_PATH.unlink()
        else:
            PASSWORD_LIST_PATH.write_text(content, encoding="utf-8")

    # -- entries --------------------------------------------------------

    def load(self) -> list[Entry]:
        raw = self._read_raw()
        entries = []
        for line in raw.splitlines():
            if not line.strip():
                continue
            entries.append(Entry.from_line(line))
        return entries

    def _save(self, entries: list[Entry]) -> None:
        content = "\n".join(e.to_line() for e in entries)
        if content:
            content += "\n"
        self._write_raw(content)

    def add(self, password: str, tag: str = "", apply_rules: bool = False, timestamp: bool = True) -> bool:
        """Add a password. Returns False if it was already present (no-op).

        apply_rules=False (the default) stores the password as-is: it will
        still appear in the generated wordlist, but create-list will not
        run any mutation rule on it.
        """
        entries = self.load()
        if any(e.password == password for e in entries):
            self._log(f"'{password}' already in store, skipping duplicate")
            return False
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds") if timestamp else ""
        entries.append(Entry(password=password, tag=tag, timestamp=ts, apply_rules=apply_rules))
        self._save(entries)
        self._log(f"added '{password}' (tag={tag or '-'}, rules={'on' if apply_rules else 'off'})")
        return True

    def remove_by_password(self, password: str) -> bool:
        entries = self.load()
        new_entries = [e for e in entries if e.password != password]
        if len(new_entries) == len(entries):
            return False
        self._save(new_entries)
        return True

    def remove_by_tag(self, tag: str) -> int:
        entries = self.load()
        new_entries = [e for e in entries if e.tag != tag]
        removed = len(entries) - len(new_entries)
        if removed:
            self._save(new_entries)
        return removed

    def clear(self) -> int:
        entries = self.load()
        self._save([])
        return len(entries)

    def import_file(self, path: Path, tag: str = "", apply_rules: bool = False) -> tuple[int, int]:
        """Import newline-separated passwords from a file. Returns
        (added_count, skipped_count)."""
        text = path.read_text(encoding="utf-8", errors="replace")
        added = 0
        skipped = 0
        for line in text.splitlines():
            pw = line.strip()
            if not pw:
                continue
            if self.add(pw, tag=tag, apply_rules=apply_rules):
                added += 1
            else:
                skipped += 1
        return added, skipped
