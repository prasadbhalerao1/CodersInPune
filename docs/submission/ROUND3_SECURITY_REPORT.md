# Relay: security report (Round 3)

The full evidence is in [security.md](security.md): the OWASP ASVS Level 2 mapping to code and
tests, and the latest dependency and secret scans. This page summarises it.

| Area | Result |
|---|---|
| Dependency audit (frontend, production) | `pnpm audit --prod`: no known vulnerabilities |
| Dependency audit (backend) | `pip-audit`: no known vulnerabilities |
| Secrets in the repository | Pattern scan: none; `.env` files are never tracked |
| Tenant isolation | Forced row-level security on every tenant table, plus a separate membership check and `authorize()` in every service; `tests/security/test_tenant_isolation.py` and `test_schema_conventions.py` |
| Signed-out access | All 100 production `GET` routes return 401/403/404 without a session; none return a 5xx |
| Roles | 8 roles from one deny-by-default registry; read-only roles (auditor, guest) are refused on every write (`test_new_features_access.py`); the public roles table is checked against the registry (`test_role_docs.py`) |
| AI | Evidence the viewer can't see never reaches a model; source text is treated as untrusted data; models have read-only tools and only propose |
| Business rules | Separation of duties; completion needs done tasks, met readiness and the incoming owner's acceptance; idempotent creates |
| Accessibility | axe-core (WCAG 2.2 AA): no serious or critical issues on `/` and `/docs` |

There are no known critical vulnerabilities and no known cross-tenant access paths.
Production credentials are rotated at the end of the evaluation period.
