---
name: Dev tools setup
overview: Set up Biome (TS/JS), Ruff (Python), cargo fmt/clippy (Rust), and shellcheck (shell) with lefthook for pre-commit formatting and pre-push lint enforcement.
todos:
  - id: install-deps
    content: Install Biome and lefthook via pnpm
    status: completed
  - id: biome-config
    content: "Create biome.json with scope: app/, vite.config.ts, scripts/prebuild.js"
    status: completed
  - id: ruff-config
    content: Create ruff.toml scoped to python/
    status: completed
  - id: pnpm-scripts
    content: Add lint:*, format:* scripts to package.json
    status: completed
  - id: lefthook-config
    content: Create lefthook.yml with pre-commit (format + stage) and pre-push (lint + typecheck)
    status: completed
  - id: lefthook-prepare
    content: Add prepare script for auto-install of hooks
    status: completed
  - id: initial-format
    content: Run pnpm format to reformat all existing code
    status: completed
  - id: verify
    content: "Test: commit with bad formatting (should auto-fix), push with lint error (should block)"
    status: completed
isProject: false
---

# Dev Tools: Lint, Format, and Git Hooks

## Tools

- **TypeScript/JS**: Biome (lint + format)
- **Python**: Ruff (lint + format)
- **Rust**: `cargo fmt` + `cargo clippy`
- **Shell**: shellcheck
- **Git hooks**: lefthook (pre-commit: format; pre-push: lint)

## 1. Install dependencies

```bash
pnpm add -D @biomejs/biome lefthook
```

Ruff and shellcheck are system tools (not npm). Add install instructions to [BUILD.md](BUILD.md) and ensure CI installs them if we ever add a CI lint job.

- Ruff: `pip install ruff` (or `brew install ruff`)
- shellcheck: `brew install shellcheck` / `apt-get install shellcheck`

## 2. Biome config

Create [biome.json](biome.json) at repo root:

```json
{
  "$schema": "https://biomejs.dev/schemas/2.0.0/schema.json",
  "files": {
    "include": ["app/**", "vite.config.ts", "scripts/prebuild.js"]
  },
  "formatter": {
    "indentStyle": "tab"
  },
  "linter": {
    "rules": {
      "recommended": true
    }
  }
}
```

**Scope**: `app/`, `vite.config.ts`, `scripts/prebuild.js`. Excludes `node_modules`, `dist`, `src-tauri` (Rust), `python/` automatically since they're not in `include`.

Note: `indentStyle` TBD based on current codebase convention -- will check and match.

## 3. Ruff config

Create [ruff.toml](ruff.toml) at repo root:

```toml
src = ["python"]
line-length = 88

[lint]
select = ["E", "F", "I", "W", "UP"]
```

Scoped to `python/` dir in scripts. Rules: pyflakes (F), pycodestyle (E/W), isort (I), pyupgrade (UP).

## 4. pnpm scripts in [package.json](package.json)

```json
{
  "scripts": {
    "lint": "pnpm lint:ts && pnpm lint:python && pnpm lint:rust && pnpm lint:shell",
    "lint:ts": "biome check app/ vite.config.ts scripts/prebuild.js",
    "lint:python": "ruff check python/ && ruff format --check python/",
    "lint:rust": "cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings",
    "lint:shell": "shellcheck scripts/*.sh",

    "format": "pnpm format:ts && pnpm format:python && pnpm format:rust",
    "format:ts": "biome check --write app/ vite.config.ts scripts/prebuild.js",
    "format:python": "ruff format python/ && ruff check --fix python/",
    "format:rust": "cargo fmt --manifest-path src-tauri/Cargo.toml"
  }
}
```

Keep existing `typecheck`, `python:typecheck`, `test:*` scripts unchanged.

## 5. Lefthook config

Create [lefthook.yml](lefthook.yml) at repo root:

```yaml
pre-commit:
  commands:
    biome:
      glob: "*.{ts,tsx,js,jsx,json}"
      run: pnpm biome check --write {staged_files}
      stage_fixed: true
    ruff-format:
      glob: "*.py"
      run: ruff format {staged_files}
      stage_fixed: true
    ruff-fix:
      glob: "*.py"
      run: ruff check --fix {staged_files}
      stage_fixed: true
    rustfmt:
      glob: "*.rs"
      run: cargo fmt --manifest-path src-tauri/Cargo.toml
      stage_fixed: true

pre-push:
  commands:
    biome:
      glob: "*.{ts,tsx,js,jsx,json}"
      run: pnpm lint:ts
    ruff:
      run: pnpm lint:python
    clippy:
      run: pnpm lint:rust
    shellcheck:
      glob: "*.sh"
      run: pnpm lint:shell
    typecheck:
      run: pnpm typecheck
```

Key behaviors:

- **pre-commit**: formatters run on staged files, `stage_fixed: true` auto-adds formatted changes back to the commit
- **pre-push**: full lint suite runs; push fails if any check fails

Add `"prepare": "lefthook install"` to `package.json` scripts so hooks auto-install after `pnpm install`.

## 6. Initial formatting pass

After setup, run `pnpm format` once to reformat all existing code. Commit as a standalone "chore: format codebase" commit so git blame stays clean (can add `.git-blame-ignore-revs` with that commit hash later).

## Edge cases and notes

- `**scripts/prebuild.js**`: included in Biome scope since it's JS
- `**vite.config.ts**`: included in Biome scope since it's a root TS config
- **JSON files**: Biome can format JSON too (package.json, tsconfig.json, etc.). Include or exclude based on preference -- plan includes only the TS/JS files for now, can expand to `"*.json"` in Biome config.
- **Partial staging**: `stage_fixed: true` in lefthook handles this correctly -- it only re-stages the files that were originally staged
- `**--no-verify` bypass: anyone can skip hooks with `git push --no-verify`. If this is a concern later, add a CI lint job (ubuntu-only, fast) as a safety net
- **Rust edition**: `cargo fmt` respects `edition = "2021"` from [src-tauri/Cargo.toml](src-tauri/Cargo.toml) automatically, no `rustfmt.toml` needed unless custom formatting is wanted
- **shellcheck**: read-only linter (no auto-fix), so it only appears in pre-push and `lint:shell`, not in format/pre-commit
- **mypy/typecheck**: kept separate from lint scripts since type checking is slower and conceptually different; included in pre-push for full validation
