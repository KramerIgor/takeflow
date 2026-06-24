# Paid Safety Checklist

Require explicit confirmation before:

- Starting Single Generation.
- Clicking or confirming `Regenerate`.
- Starting Queue processing.
- Running Night Mode paid execution.
- Running continuation chains that submit tasks.
- Running scripts with names such as `run_*paid*`, `test_generate*`, or Segmind auth/generation checks.
- Reading or editing `.env`.
- Changing API client submission behavior.

Allowed without paid confirmation:

- Reading source code except secrets.
- Editing UI/backend code.
- Running compile checks.
- Running safe diagnostics documented as dry-run or preview-only.
- Opening the GUI and stopping before paid confirmation.
