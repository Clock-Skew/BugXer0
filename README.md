# BugXer0

![BugXer0 logo](Bug-Zero-logo-white.webp)

**Current release:** 0.1.1

BugXer0 is a streamlined command-line tool for security researchers who
triage newly disclosed CVEs or hunt for 0-days in open-source codebases.
It wraps the GitHub code search API to quickly scan repositories for
vulnerable patterns.

## Goals
- Hands-on experience tailored for bug hunters (fast, scriptable, reliable).
- Safe token handling with zero hard-coded credentials.
- Modular code that is easy to extend and open source.

## Key Features
- `bugzero search`: Run a single query string or multi-line query file.
- `bugzero sweep`: Execute a batch of named queries from a managed list.
- GitHub token sourced from the environment or an optional config file
  stored outside version control (e.g. `~/.config/bugzero/config.json`).
- Structured JSON or human-readable output.


## Usage
### Install
Requires Python 3.10+. Inside `v2/` you can install the CLI as an editable package:
```
pip install -e .
```
If your system Python is externally managed, create a virtual environment first
(`python -m venv .venv && source .venv/bin/activate`).

### GitHub token
BugZero pulls credentials from the `GITHUB_TOKEN` environment variable or from
`~/.config/bugzero/config.json`. Recommended workflow:
1. Export it for the current shell:
   ```
   export GITHUB_TOKEN=ghp_example123
   ```
2. Or persist it via the CLI:
   ```
   bugzero token set
   ```
   (Prompts securely and writes to `~/.config/bugzero/config.json`.)
3. Confirm where the token will be sourced:
   ```
   bugzero token info
   ```

#### How to obtain a GitHub token
1. Visit https://github.com/settings/tokens/new (choose fine-grained or classic).
2. Give the token a descriptive name and expiration.
3. Grant scopes such as `public_repo` (plus `repo` if you need private repos).
4. Generate and copy the token immediately—GitHub only shows it once.
5. Load it into BugZero using the steps above.

### Search examples
Run a quick scan for outdated OpenSSL references:
```
bugzero search -q "OpenSSL 1.0.2" -Q language=c -Q path=openssl
```

Search multiple signatures from a file, each line treated as a separate query:
```
bugzero search --query-file signatures/openssl.txt --split-lines -Q repo=org/project
```

Fetch two pages of 50 results and return JSON:
```
bugzero search -q "strcpy(" -Q language=c --per-page 50 --pages 2 --output json
```

### Saved queries
Store a recurring hunt:
```
bugzero queries add heartbleed --query "SSL3_ALERT_HANDSHAKE_FAILURE" -Q language=c
```

List saved hunts:
```
bugzero queries list
```

Execute all saved queries and dump structured JSON:
```
bugzero sweep --output json
```

Target specific saved queries with extra qualifiers:
```
bugzero sweep heartbleed shellshock -Q repo=myorg/legacy-app
```
