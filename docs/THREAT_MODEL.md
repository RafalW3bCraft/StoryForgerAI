# Threat model — AI StoryForge MVP

| Threat | Boundary | Controls implemented | Remaining risk |
|---|---|---|---|
| Viewer impersonation | Twitch → Persona | Sender Twitch ID from EventSub; browser profile binds OAuth identity | Live OAuth not yet verified |
| Unauthenticated host actions | Browser → Host Studio | Signed session role; host ID checks; CSRF fields | Demo password attempts not rate limited; bind demo to loopback |
| Stored XSS | Chat → UI | Jinja2 autoescaping; text length bounds; no authored scripts; SVG is generated from bounded attributes | Security review and browser penetration test pending |
| OAuth state substitution | Twitch → Callback | Random state stored in signed session and checked | No deployment verification behind HTTPS reverse proxy |
| Token disclosure | DB → Twitch | Fernet encrypted vault; no tokens in web session | Encryption key and DB together expose tokens; key rotation not implemented |
| Prompt injection | Viewer → AI | Explicitly bounded, structured content; no arbitrary model tools; host proposal review | LLM can still produce undesirable fiction; moderation policy basic |
| Duplicate vote/event | EventSub → DB | Unique message receipt and effective vote per user/round | One-process assumption; no long-term event retention cleanup |
| AI cost exhaustion | Host → Provider | Host-authenticated generation; timeouts, one-generation stage at a time; demo mode cannot implicitly enable external AI | No explicit per-day token/currency budget |
| Story-state corruption | Host/Viewer → SQLite | Transactional writes, validated stages, persisted pause origin, partial unique open-round index, preserved fork history | SQLite concurrency and crash injection tests incomplete |
| Privacy overcollection | Persona → Storage | Stores fictional profile and stable Twitch ID, no raw media; deletion pseudonymizes | Retention schedule and full privacy impact assessment pending |
| OBS privilege escalation | Public overlay → Host | Overlay GET only; host POST actions require authenticated session + CSRF | Needs deployed CSP assessment |
| Host replay after logout | Browser cookie | Logout clears signed session, secure cookies behind HTTPS | Session revocation beyond logout not implemented |

The MVP is **not independently security-audited**. Available static scanners (Bandit, pip-audit, Trivy, Gitleaks) were not installed in this environment. Do not expose the demo app to the internet or represent it as production-ready. The local `.env` contains configured-looking credentials; rotate them before publication or live use.
