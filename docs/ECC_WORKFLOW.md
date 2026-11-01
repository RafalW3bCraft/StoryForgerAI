# ECC + Codex integration status

**Partially applied, not submission evidence.** Codex CLI 0.166.0 is present and the ECC 2.2.3 marketplace checkout is readable, but `codex plugin list --json` reported `installed: []`; the native plugin is not registered in this runtime. No `$configure-ecc` invocation or ECC agent run can be claimed. The repository also has an empty `.git` directory, so verifiable local commits cannot be produced here.

For this Codex session, the available ECC guidance was read and applied as engineering review guidance:

- `tdd-workflow`: tests were added for the voting regression, bounded context, malformed AI responses, and EventSub revocation before implementation verification.
- `security-review`: OAuth/state/identity binding, secret handling, CSRF, XSS, prompt-injection boundaries, duplicate delivery, and token redaction were reviewed.
- `verification-loop`: Ruff, formatting, mypy, compilation, targeted tests, coverage, and external-integration checks were run and recorded.

These are truthful skill-guidance uses, not proof that the ECC plugin executed inside Codex. The local Codex session index identifies this turn as `01a1959c-5725-74e1-afc2-c3d3e45f1091`; the operator must confirm that ID with `/status` in the primary Codex UI before submission.

The installed GitHub ECC upstream documents a native Codex plugin integration. On the operator's Codex machine, inspect current CLI version and use the official procedure when compatible:

```bash
codex plugin marketplace add affaan-m/ECC
codex plugin add ecc@ecc
codex plugin list --json
```

Then use `$configure-ecc` inside Codex if available. Do not combine native plugin installation with ECC's deprecated legacy sync path. Read https://github.com/affaan-m/ECC/blob/main/.codex-plugin/README.md before changing the environment.

For the continued project: open a Codex session in this repository, read `AGENTS.md`, use available ECC TDD/security/Python review workflows, fix the findings, run tests and record evidence in `docs/CODEX_BUILD_LOG.md`. Capture the actual `/status` session ID from the Codex thread where the substantive development work occurs. **This file does not substitute for actual tool-use evidence.**
