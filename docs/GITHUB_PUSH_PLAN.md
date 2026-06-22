# GitHub Push Plan — secret hygiene & checklist

Plan only. Nothing here has been executed. Run the checklist before the first push.

## The API key situation — assessment

- The Kimi/Moonshot key lives **only in `.env`**, which is `.gitignore`d and has **never been
  tracked** (verified: `git check-ignore .env` → ignored; the key string appears in no
  committed file). So **the key will not be in the pushed repository.**
- However, the key **was pasted in plaintext into the chat/agent transcript** during setup.
  The repo is clean, but the key's secrecy already depends on that transcript staying private.

### Recommendation on the key

1. **Before pushing:** confirm it is not tracked or in history (commands below).
2. **Regardless of the repo being clean: rotate the Kimi key.** It was shared in plaintext in a
   conversation; rotating is cheap insurance and the only way to be certain. Generate a new key
   in the Moonshot console, put it in `.env`, revoke the old one. Do this **before** the repo is
   public if it ever will be.
3. Never commit `.env`. Keep `.env.example` with placeholders only (already the case).

## Pre-push checklist

```bash
# 1. Confirm .env is ignored and untracked
git check-ignore .env                      # must print ".env"
git ls-files | grep -E '(^|/)\.env$'       # must print NOTHING

# 2. Scan the whole history for the key fragment and common secret patterns
git log -p | grep -i "sk-pSDa"             # must print NOTHING (key fragment)
git log -p | grep -iE "api_key|secret|private_key|sk-[A-Za-z0-9]{20}" | head

# 3. Scan tracked files for secrets right now
git grep -iE "sk-[A-Za-z0-9]{20}" -- ':!*.example' || echo "clean"

# 4. (Recommended) run a real scanner before going public
#    pipx run gitleaks detect --source . --no-banner
```

If any of 1–3 surfaces the key, **stop** and scrub before pushing (see "If a secret is found").

## What to commit vs ignore (already configured)

Ignored (`.gitignore`): `.env`, `*.db` / WAL, `__pycache__`, `.venv/`, `node_modules/`,
`dist/`, `workspace/state/` (lock + runtime override), and the live `workspace/construct/*.md`
(templates are kept). Confirm `frontend/dist/` is not committed (build artifact).

Committed: source, `docs/`, `.env.example`, `pyproject.toml`, `Makefile`, frontend source +
`package-lock.json`, `.claude/launch.json`.

## Repository setup

```bash
# Create the repo (private first is safest while reviewing)
gh repo create littleman --private --source . --remote origin
git push -u origin main
```

- Start **private**. Only flip to public after the key is rotated and the history scan is clean.
- Enable **GitHub secret scanning** + **push protection** (Settings → Code security) so a future
  accidental secret commit is blocked.
- Consider a **pre-commit hook** with `gitleaks` so secrets never reach a commit locally.

## If a secret is ever found in history

Do not just delete it in a new commit — it stays in history. Use
`git filter-repo` (preferred) or BFG to purge it, force-push, and **rotate the secret** (purging
history does not un-leak an already-pushed key). Because we never tracked `.env`, this should
not be necessary — but rotate the Kimi key anyway per the recommendation above.

## Notes for collaborators / README

Add a short "Setup" note (README already has one): copy `.env.example` → `.env`, add your own
LLM key, never commit `.env`. The agent's runtime LLM is also editable live in the UI
(Settings → Agent runtime), which writes to `workspace/state/runtime.json` (also ignored).
