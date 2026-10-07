# kudzu

> Turn the passwords you find during an audit into the passwords you'll find next.

![version](https://img.shields.io/badge/version-0.1.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

## What it does

During a pentest you often crack or dump a handful of real passwords. kudzu stores them and grows each one into a wordlist of likely variants (year changes, leet speak, case changes, symbols...), so you can spray that short, targeted list instead of throwing rockyou.txt at every account.

```bash
kudzu add "Summer2022" --tag kerberoast --rules
kudzu create-list wordlist.txt --keyword Acme
netexec smb targets.txt -u users.txt -p wordlist.txt --continue-on-success
```

## Install

```bash
git clone https://github.com/ned0x1/kudzu.git && cd kudzu && pip install -e .
```

Requires Python 3.10+. `gpg` on PATH if you want encrypted storage.

## Commands

### `kudzu add <password>`
Stores a password. `--tag` labels where it came from. `--rules` decides whether `create-list` will mutate it | without `--rules` the password is still stored and still ends up in the final wordlist, just untouched.

```bash
kudzu add "Welcome2024" --tag ldap --rules
kudzu add "xK9#mQ2vL8pZ" --tag "mail jdupont"   # random, no point mutating it
```

### `kudzu create-list <output>`
Generates the wordlist from everything stored. `--keyword` folds an extra word (company/target name) into the mutations.

```bash
kudzu create-list spray.txt --keyword Acme
```

### `kudzu list`
Shows every stored password, its tag, and whether rules are on.

### `kudzu remove`
Deletes one password or a whole tag's worth:

```bash
kudzu remove --password "Welcome2024"
kudzu remove --tag "mail jdupont"
```

### `kudzu clear`
Wipes the store.

### `kudzu import <file>`
Bulk-adds passwords from a file (e.g. a `secretsdump` or Hashcat output). `--tag` and `--rules` apply to every line.

### `kudzu where`
Prints where the store and config live.

## How the mutations work

Only applies when a password was added with `--rules`. Five rules, all toggleable in `~/.kudzu/config.yaml`:

| Rule | What it does | Example |
|---|---|---|
| Year range | A 4-digit year in the password (1800–now) is expanded to every year up to now+2, plus 2-digit and separator forms | `Corp2022` → `Corp2023`...`Corp2028`, `Corp26`, `Corp_2026` |
| Digit range | A number that isn't a year gets ±10 around it, same digit width | `Corp042` → `Corp032`...`Corp052` |
| Case powerset | Every upper/lower combination of each letter | `Fox` → `fox`, `Fox`, `fOx`, `foX`, `FOx`, `FoX`, `fOX`, `FOX` |
| Leet speak | Full-string substitution | `password` → `p4$$w0rd` |
| Symbol wrap | A symbol added before or after | `Corp2026` → `!Corp2026`, `Corp2026!` |

`--keyword` combines an extra word with the same year logic (`--keyword Acme` on a password containing `2022` also produces `Acme2022`...`Acme2028`).

The year/digit-range results are always kept in full; only the case/leet/symbol combinations on top are trimmed if the total goes past `limits.max_variants_per_password` (5000 by default).

## Storage

`~/.kudzu/password/list.txt` | one password per line, tab-separated: `password, tag, timestamp, rules-flag`. Plaintext by default.

Set `storage.encryption: gpg` in the config to encrypt it (prompts for a passphrase on every read/write, no plaintext left on disk, requires the `gpg` binary).

## Good practice

- Spray one password across many accounts rather than brute-forcing one account | far less likely to trigger a lockout.
- Check the target's lockout policy first and leave headroom under the bad-attempt counter.
- Keep `--rules` for passwords with a human pattern; leave it off for random/high-entropy ones | mutating those just adds noise.
- Use this only on engagements you're authorized to test.

## License

MIT | see [LICENSE](LICENSE).
