# E2E Affected Tests POC (Phase 0)

AI-driven selection of which E2E (Playwright) tests to run from a **git diff**. The script prints **changed files**, the **model response**, **selected test paths**, and a suggested `npx playwright test ...` command. It does **not** run Playwright itself.

Tests are **discovered automatically**: all `**/*.spec.js` files under `Worklist-2/playwright/` (sorted paths, forward slashes). `generate_summaries.py` and `select_tests.py` share the same discovery logic in `scripts/select_tests.py` (`discover_playwright_spec_paths`). Optional snapshot for humans/docs: `playwright_spec_paths.txt` (not read by the scripts).

This folder may live in the monorepo as **`Test_selection1/`** (or a copy named `E2E-Affected-Tests-POC/`); paths below use `Test_selection1/scripts` — adjust to match your layout.

## Requirements

- **Python 3** + `pip`
- **Git** (for `git diff` when using `--base` / `--head`)
- **OmegaAI-Mono** (or equivalent) cloned locally — contains `Worklist-2/playwright/` and the app code you diff against
- **Azure OpenAI** deployment (chat completions), credentials in `scripts/.env` (see `.env.example`)

## Windows (PowerShell)

On Windows, set UTF-8 before running so `git diff` and console output don’t hit encoding errors:

```powershell
$env:PYTHONUTF8 = "1"
cd C:\path\to\OmegaAI-Mono\Test_selection1\scripts
```

## Quick start

```bash
cd Test_selection1/scripts
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your Azure values
python generate_summaries.py --repo /path/to/OmegaAI-Mono
python select_tests.py --repo /path/to/OmegaAI-Mono --base master --head HEAD
```

If this folder lives **inside** OmegaAI-Mono (e.g. `OmegaAI-Mono/Test_selection1/scripts/`):

```bash
python generate_summaries.py --repo ..\..
python select_tests.py --repo ..\.. --base master --head HEAD
```

## Run modes (commands)

Use real git SHAs or branch names — **do not** use angle brackets in PowerShell (they redirect).

| Mode | Command |
|------|---------|
| **Single-shot** (default) | `python select_tests.py --repo REPO_PATH --base OLD_REF --head NEW_REF` |
| **Single-shot**, full spec text | Add `--approach full` (high token use). |
| **Two-stage**, Stage 2 **precision** (default) | Add `--two-stage` |
| **Two-stage**, Stage 2 **balanced** (slightly more tests than precision) | Add `--two-stage --stage2-balanced` |
| **Two-stage**, Stage 2 **recall** (widest list) | Add `--two-stage --stage2-recall` |
| **Dry-run** (no API) | Add `--dry-run` to any of the above |

`--stage2-balanced` and `--stage2-recall` **cannot** be used together.

Examples:

```bash
# Single-shot (summaries)
python select_tests.py --repo /path/to/OmegaAI-Mono --base master --head HEAD

# Two-stage, default precision Stage 2
python select_tests.py --repo /path/to/OmegaAI-Mono --base master --head HEAD --two-stage

# Two-stage, balanced Stage 2
python select_tests.py --repo /path/to/OmegaAI-Mono --base master --head HEAD --two-stage --stage2-balanced

# Two-stage, recall Stage 2
python select_tests.py --repo /path/to/OmegaAI-Mono --base master --head HEAD --two-stage --stage2-recall
```

## Configuration

Copy `scripts/.env.example` → `scripts/.env` and set:

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_API_KEY` | API key |
| `AZURE_OPENAI_ENDPOINT` | Resource URL (no path suffix) |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment name |
| `AZURE_OPENAI_API_VERSION` | e.g. `2025-04-01-preview` (match your resource) |
| `AZURE_OPENAI_TIMEOUT_SECONDS` | (Optional) HTTP client timeout in seconds; omit for SDK default. |
| `AZURE_OPENAI_SELECTION_MAX_COMPLETION_TOKENS` | (Optional) Single-shot; default **8192**. |
| `AZURE_OPENAI_STAGE1_MAX_COMPLETION_TOKENS` | (Optional) Two-stage Stage 1; default **16384**. |
| `AZURE_OPENAI_STAGE2_MAX_COMPLETION_TOKENS` | (Optional) Two-stage Stage 2; default **16384**. |
| `STAGE2_MAX_TOTAL_SNIPPET_CHARS` | (Optional) Total character budget for all Stage 2 spec snippets; default **100000** (avoids huge prompts when Stage 1 returns many paths). |
| `STAGE2_FALLBACK_STAGE1` | (Optional) Set to `1` / `true` / `yes`: if Stage 2 returns empty text, use Stage 1 candidates. |
| `SELECT_TESTS_VERBOSE_AZURE` | (Optional) Set to `1` for extra stderr diagnostics. |

**Deployment limits:** Azure **gpt-4o** typically allows **at most 16384** completion tokens per request. Values above that return HTTP 400. Some models (e.g. **gpt-5-mini**) may spend tokens on internal reasoning; if Stage 2 returns empty `message.content`, try another deployment, adjust prompts, or use `STAGE2_FALLBACK_STAGE1`.

## Scripts

| Script | Purpose |
|--------|---------|
| `generate_summaries.py` | Calls Azure OpenAI to build `test_summaries.json` (one-line description per test). Run when tests change. |
| `select_tests.py` | Builds prompt from diff + summaries, calls Azure OpenAI, outputs selected paths and suggested Playwright command. |

### `select_tests.py` options

- `--repo` – Root of the app repo (default `../OmegaAI-Mono` if run from elsewhere).
- `--base`, `--head` – Git refs for `git diff` (defaults: `master`, `HEAD`).
- `--diff-file` – Use a saved unified diff instead of `git diff`.
- `--approach` – `summaries` (default) or `full` (send full spec content; needs more tokens). Used for **single-shot** mode only.
- `--two-stage` – **Two-step** pipeline: **Stage 1** calls the model once with path + summary for every discovered spec (**wide net**; no fixed cap on candidate count). **Stage 2** calls the model again with the diff plus **truncated** spec file contents (per-spec cap derived from `STAGE2_MAX_TOTAL_SNIPPET_CHARS`) for those candidates and outputs the **final** path list. **Stage 2 defaults to precision-first** (smallest sufficient set for *this* diff). Ignores `--approach` (Stage 1 uses summaries; Stage 2 uses snippets). Writes **final paths** (one per line) to `last_model_response.txt`; **raw Stage 2** text to `last_model_raw_response.txt`; **merge-only** paths to `last_stage2_merged_paths.txt`.
- `--stage2-balanced` – **With `--two-stage` only.** Stage 2 uses a **balanced** prompt: slightly **more** tests than precision-default (e.g. several paths when multiple flows plausibly apply). Mutually exclusive with `--stage2-recall`.
- `--stage2-recall` – **With `--two-stage` only.** **Recall-first** Stage 2 prompt (keep every plausible candidate from Stage 1). Mutually exclusive with `--stage2-balanced`. Omit both for default precision Stage 2.
- `--dry-run` – Build prompt only; no API call.

### Selection behavior

**Single-shot (default, no `--two-stage`):** One model call using `--approach`. The prompt aims for a **minimum** justified set.

**Two-stage (`--two-stage`):** Stage 1 is **recall-oriented** (broad candidate list). Stage 2 behavior depends on flags: **precision** (default), **balanced** (`--stage2-balanced`), or **recall** (`--stage2-recall`). After Stage 2 (precision and balanced only), the script may **merge** Stage-1 candidates back in when they match **heuristic rules** (e.g. wheel/window-level tools; **DataGrid** + `data-cy` / worklist table → `WorklistSelection/worklistSelection.spec.js`; **OrganizationUser.jsx** + login/email copy → `User/disableLoginEmail.spec.js`). Parsed paths must come from the discovered spec list (Stage 1) or from Stage-1 candidates (Stage 2). If Stage 2 returns empty text, optional **`STAGE2_FALLBACK_STAGE1=1`** uses the Stage 1 list.

- **Successful API** + empty or unparseable model text → **no tests** selected (no `npx` line). **API failure** on Stage 1 or Stage 2 → **fallback: all discovered spec files** (safe default); warning on stderr. With a large suite, the printed `npx` line may be very long.

Artifacts (gitignored): `scripts/last_model_response.txt` (**final** selected paths, one per line, or `(none)`), `scripts/last_model_raw_response.txt` (raw assistant text: Stage 2 in two-stage, single-shot otherwise), `scripts/last_stage1_candidates.txt` (raw Stage 1 reply), `scripts/last_stage2_merged_paths.txt` (paths added only by script merge after Stage 2, or `(none)` / merge skipped when using `--stage2-recall`).

## Patch-based workflow (local only)

To simulate a change without pushing:

```bash
cd /path/to/OmegaAI-Mono
git checkout -b poc-diff-test master
git apply /path/to/patches/affects-login.patch
git add -A && git commit -m "POC: local patch"
cd Test_selection1/scripts
python select_tests.py --repo ..\.. --base master --head HEAD
```

Patch files may live in this POC repo under `example-diffs/` or in a separate folder; use the path that matches your machine.

**Do not push** `poc-diff-test` to company remotes if policy requires local-only POC work.

## Optional: run selected Playwright tests

From `OmegaAI-Mono/Worklist-2`:

```bash
npx playwright test playwright/<path-from-output> ...
```

## Standalone GitHub repo (`e2e-affected-tests-poc`)

You can copy **only this folder** to its own repository for demos. Teammates still need a local **OmegaAI-Mono** clone and must pass `--repo` to that path. Do **not** commit `scripts/.env`; use `.env.example` only.

## Folder layout

```
Test_selection1/          # or E2E-Affected-Tests-POC/ when copied
  .gitignore
  README.md
  playwright_spec_paths.txt  # optional: manual snapshot of spec paths; scripts use glob instead
  example-diffs/          # optional: .patch files for experiments
  scripts/
    .env.example
    requirements.txt
    select_tests.py
    generate_summaries.py
    test_summaries.json   # generated; may be committed for demos
```

## Ground truth (optional)

If you add **MAPPING.md**, map each patch to expected tests to score accuracy against **Selected tests** output.
