# Threat model — AI StoryForge MVP

| Threat | Boundary | Controls implemented | Remaining risk |
|---|---|---|---|
| Viewer impersonation | Twitch → Persona | Sender Twitch ID from EventSub; browser profile binds OAuth identity | Live OAuth not yet verified |
| Unauthenticated host actions | Browser → Host Studio | Signed session role; host ID checks; CSRF fields; demo login checks both loopback client IP and loopback Host | Demo password attempts are not separately rate limited; live host access must use Twitch OAuth |
| Stored XSS | Chat → UI | Jinja2 autoescaping; text length bounds; no authored scripts; SVG is generated from bounded attributes | Security review and browser penetration test pending |
| OAuth state substitution or lost session cookie | Twitch → Callback | Random state stored in signed session; pure ASGI middleware redirects every off-origin HTTP request to fixed `APP_BASE_URL` before session handling; callback errors return to app home and mismatched state is rejected before token exchange | Uvicorn access logs disabled to keep callback query strings out of logs; exact Twitch Console registration, reverse-proxy deployment and real callback remain unverified |
| Token disclosure | DB → Twitch | Fernet encrypted vault; no tokens in web session | Encryption key and DB together expose tokens; key rotation not implemented |
| Prompt injection | Viewer → AI | Explicitly bounded, structured content; no arbitrary model tools; host proposal review | LLM can still produce undesirable fiction; moderation policy basic |
| Duplicate vote/event | EventSub → DB | Unique message receipt and effective vote per user/round | One-process assumption; no long-term event retention cleanup |
| AI cost exhaustion | Host → Provider | Host-authenticated generation; timeouts; app-instance lock prevents concurrent duplicate requests; demo mode cannot implicitly enable external AI | No explicit per-day token/currency budget; lock is process-local |
| Story-state corruption | Host/Viewer → SQLite | Transactional writes, validated stages, persisted pause origin, partial unique open-round index, preserved fork history | SQLite concurrency and crash injection tests incomplete |
| Privacy overcollection | Persona → Storage | Stores fictional profile and stable Twitch ID, no raw media; deletion pseudonymizes | Retention schedule and full privacy impact assessment pending |
| OBS privilege escalation | Public overlay → Host | Overlay GET only; host POST actions require authenticated session + CSRF | Needs deployed CSP assessment |
| Host replay after logout | Browser cookie | Logout clears signed session, secure cookies behind HTTPS | Session revocation beyond logout not implemented |
| Secrets in diagnostic representations | Python `Settings` object | Secret fields have `repr=False`; sentinel regression checks representation redaction | A configured secret appeared in a failed pytest representation before the fix; rotate it before release |

The MVP is **not independently security-audited**. `pip-audit` found seven advisories in the prior `cryptography 47.0.0` pin; the requirement is now raised to `50.0.2`, and reruns report no known dependency vulnerabilities. Bandit 1.9.4 found no Medium/High issues after the diagnostic probe was changed to a fixed-name main-database table created and rolled back inside a write transaction; its 13 Low findings were reviewed as false positives for these code paths. Trivy, Gitleaks, and an independent review remain undone. Do not expose the demo app to the internet or represent it as production-ready. The local `.env` contains configured-looking credentials; rotate them before publication or live use.
