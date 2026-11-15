# Relay documentation

Start with the **[judge guide](JUDGE_GUIDE.md)** (problem, lifecycle, evidence matrix, judging
criteria) or the **[ten-minute walkthrough](../README.md#for-judges)** on the live product.

## Product

| Document | Read it for |
|---|---|
| [JUDGE_GUIDE.md](JUDGE_GUIDE.md) | Why Relay exists, the continuity lifecycle, implementation evidence and the five criteria |
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Executive overview: what Relay does, architecture, data flow, AI evaluation, operations |
| [competitive-analysis.md](competitive-analysis.md) | Adjacent products, Relay's position, and the gaps we adopted, adapted, deferred or rejected |
| [research/](research/) | Sourced research wiki (verified facts vs vendor claims) and the LLM Council transcript behind the decisions |
| [improvements.md](improvements.md) | The three Round 3 improvements as committed, with acceptance criteria |
| [round3/improvements-delivered.md](round3/improvements-delivered.md) | Each Round 3 commitment as delivered, with code and tests |
| [demo-script.md](demo-script.md) | Scripted demo on the sample workspace (*Northwind Labs*, all synthetic) |

## Technical

| Document | Read it for |
|---|---|
| [architecture.md](architecture.md) | System context, request path and security boundary, modules, data flows, reliability |
| [api-reference.md](api-reference.md) | Endpoints, authentication, permissions and examples |
| [openapi.json](openapi.json) | OpenAPI schema generated from the code |
| [ai.md](ai.md) | Evidence retrieval, citation validation, injection handling, providers and budgets |
| [trust.md](trust.md) | Privacy, security, accessibility, responsible design |
| [sso.md](sso.md) | Enterprise SSO through WorkOS |
| [../deployment.md](../deployment.md) | Vercel + Render + Neon deployment, migrations, backups |
| [runbooks/incident-response.md](runbooks/incident-response.md) | Incident response |
| [adr/](adr/) and [blueprint/](blueprint/) | Architecture decisions and the Decision Register |
| [release-audit/](release-audit/) | Release audit: traceability, security review, production readiness |

## Quality

| Document | Read it for |
|---|---|
| [round3/testing-notes.md](round3/testing-notes.md) | Test suites, browser journeys, failure cases and results |
| [round3/screenshots/](round3/screenshots/) | Screens of the delivered features |

Contributor conventions (layout, guardrails, naming, commits): [../CLAUDE.md](../CLAUDE.md).
Local setup: [../README.md → Run it yourself](../README.md#run-it-yourself).
