# Privacy, security, accessibility and responsible design

## Privacy

- **Data minimisation.** Connectors read metadata, not content, wherever that's enough:
  - GitHub: repository metadata, CODEOWNERS, `catalog-info.yaml`, and PR and issue titles and states. Never source code.
  - Linear: issue titles, states and assignees.
  - Notion: only the pages a person explicitly shares.

  Settings → Data & privacy lists what Relay reads and why.
- **No secrets in logs or audit.** Logs carry identifiers, route templates, status and duration. Audit metadata holds identifiers and enums only. Bodies, query strings, tokens and user content are never logged.
- **Secrets at rest.** Linear and Notion tokens are encrypted with `RELAY_INTEGRATION_ENCRYPTION_KEY`. GitHub installation tokens are minted per sync and never stored.
- **Retention.** Admins set a retention period (30–3650 days, default 365) for operational records: read notifications, connector run history and AI step logs. Audit events, cases, ownership history and knowledge versions are kept as the record.
- **Export and portability.**
  - Admins can export the whole workspace as JSON and the audit log as CSV.
  - Each export is itself audited.
- **Deletion.**
  - The owner schedules deletion by typing the workspace name.
  - The owner can cancel for 30 days.
  - After that an owner-role job purges every row, the audit log included.
- **Classification.** Knowledge can be public, internal, confidential or restricted. A database check makes confidential and restricted items managers-only.
- **AI.** Only evidence the requesting user may see for that case is sent to a model, and prompts aren't stored. See [ai.md](ai.md).

## Security

| Control | Implementation |
|---|---|
| Authentication | WorkOS AuthKit. The API verifies every access token (JWKS, issuer, audience, expiry, algorithm) |
| Tenant isolation | Membership-derived tenant; transaction-local context; forced RLS on every tenant table; composite tenant FKs; app role without `BYPASSRLS`. Tested as the real role |
| Authorization | Central permission registry. Every service authorizes, lists use `visible()`, and unknown roles or permissions are denied. Separation of duties on critical approvals |
| Restricted data | Restrictive RLS policy, so it fails closed even if a service is wrong |
| Input | Strict request models (unknown fields rejected); length limits; enum validation; rate limits on abuse-prone endpoints |
| Integrity | Append-only audit log and ownership history (grant and trigger). Idempotency keys on creating requests and external writes |
| Webhooks | HMAC signature over the raw body checked before parsing; deliveries deduplicated |
| OAuth | Connection state is random, stored only as a hash and checked on callback. GitHub installs are verified against the installing user, not just the `installation_id` |
| Integrations | Read-only by default. Writes need a config flag, write scope, and approval of exact content |
| Supply chain | Pinned lockfiles, SBOM per build, image vulnerability scan, licence gate (no GPL, AGPL, SSPL, BSL or SUL) |
| Production surface | API docs and OpenAPI disabled in production. Only the web app is public in the Compose deployment |
| Ops | Migrations need the owner role (kept out of the app). Backups with a restore drill. [Incident runbook](runbooks/incident-response.md) |

Report a vulnerability privately to the maintainer; don't open a public issue.

## Accessibility

- Semantic HTML: landmarks, headings in order, `<label>` for every input, `<dl>` and lists for data.
- Everything works with a keyboard. Focus is visible, the command menu opens with `Ctrl/⌘ K`, and dialogs trap and return focus (Base UI).
- Status is never shown by colour alone. Badges have text, and colour is reserved for meaning (risk, status), never decoration.
- Form errors are announced (`role="alert"`), and submit buttons show their pending state. Skeletons keep layout stable while loading.
- Respects `prefers-color-scheme` and `prefers-reduced-motion`. The landing walkthrough pauses on hover and focus.
- Layouts work from 320 px phones up. On small screens navigation moves into a disclosure menu.

Known gap: no formal WCAG 2.2 audit with assistive-technology users yet.

## Responsible design

- **Not a surveillance tool.** Relay tracks responsibilities and handovers, not individual productivity.
  - It has no activity scoring.
  - Insights are team-level trends with stated denominators and limitations.
- **People decide.** AI and rules propose, and a person accepts, edits or rejects. Ownership is never silently overwritten: imports and AI create suggestions, and changes go through cases with approvals.
- **Honest about uncertainty.** Stale, partial or missing sources are shown as such, and AI inferences are labelled.
- **Transparency to the affected person.**
  - Omissions are listed, so the recipient knows what they can't see.
  - Denials explain which role would be needed.
- **Consent to share.** Privacy review on cases lets managers decide what a recipient sees, and redactions are recorded.

## Limitations

- **Integrations.**
  - GitHub, Linear and Notion only.
  - Linear and Notion changes arrive by scheduled and manual sync; GitHub has webhooks.
  - Slack, Jira, Confluence and Google Drive are not connected.
- **Handovers.** In-app only. There is no PDF export yet.
- **Change flagging.** "Changed since review" isn't flagged automatically when a cited source's revision changes. Withdrawn sources are handled. See [improvements.md](improvements.md).
- **Notifications.** Email covers case, task and invitation notifications. Integration and security alerts are in-app.
- **Scheduled jobs.** Need the worker running. Missed runs catch up on the next schedule.
- **SSO and SAML.** Configured per organisation in WorkOS. Relay doesn't sync SCIM groups to roles yet. See [sso.md](sso.md).
- **Validation.** Tested on synthetic data and by the builder, not yet in a customer pilot. The baselines in the Round 1 plan haven't been measured with a real team.
