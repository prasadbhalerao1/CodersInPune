# Relay walkthrough: script to read while screen recording

Record your main screen (Windows: Win+Alt+R with Xbox Game Bar, or OBS). Start at https://relay-continuity-nine.vercel.app and click through each chapter in order. Read the text while doing what it describes. About 20-25 minutes.

## 1. Relay

Hello judges. Picture this. It's Friday afternoon, and Arjun, the engineer who runs your production deployments, hands in his notice. Who else knows how to roll back a bad release? Where is the runbook, and is it still right? Which decisions did he make that nobody wrote down? In most companies the honest answer is: nobody is sure. That is the problem Relay solves. Relay is an organisational continuity platform from team Midnight Ciphers. It knows who is accountable for what, rebuilds the context behind that work from GitHub, Linear and Notion with cited evidence, forecasts what an absence would break before it happens, and moves ownership through a reviewed, audited handover, and then checks that the handover actually took hold. Over the next half hour I will show you every feature, live, exactly as a new user would use it, with no cuts.

## 2. Landing page

This is where a team first meets Relay. It states the problem in three cards: single owners, scattered context and unclear handovers. Below, an interactive walkthrough plays the whole loop: a change happens, Relay gathers evidence instead of guesses, people decide, the handover fits the recipient, and ownership moves. Then the product areas: the responsibility catalogue, continuity cases, evidence-backed analysis, handover capsules, governed knowledge and read-only connections. And the trust section: AI only drafts proposals and holds no write tools, every tenant is isolated with Postgres row-level security, and gaps in the sources are shown, never filled in by a model. The public site also publishes a robots file, a sitemap, an llms dot t x t file and structured data, so search engines and AI agents can read what Relay is.

## 3. Sign in and the sample workspace

Let's go to the workspaces. Sign-in is handled by WorkOS with a one-time email code, so Relay never sees a password, and signing in grants access to nothing until you are a member of a workspace. Here I can create an empty workspace for my own data, or a sample workspace. I'll create the sample: Northwind Labs, a fictional company with eight people, seven responsibilities and a year of synthetic GitHub, Linear and Notion history. One engineer, Arjun Rao, is leaving. Everything in it is labelled as sample data.

## 4. Overview

This is the Overview. Because product guidance is on, Relay suggests a short tour and shows a setup checklist with essential and optional steps. Each item is computed from real records, and a connected tool only counts as ready after its first sync has finished. Next is continuity health: the share of critical work that has an owner, a backup and current knowledge, broken down by severity, together with the continuity debt score. Below are the counts: active responsibilities, work without a primary owner, critical work without a backup, and open continuity risks. Needs attention lists each gap with the rule that raised it. On the right are the handovers in motion, and further down the top risks and recent ownership changes. Nothing here is estimated; every number links to the records behind it. In ten seconds, a manager knows where the organisation is fragile.

## 5. Learn Relay: guidance and tours

New users can open Learn Relay from the sidebar. The product guidance switch is per person: when it is off, Relay stops showing automatic tips and the checklist, but every tutorial still works. There are eight tours, and each one only unlocks when the workspace has the data it shows, so nobody is sent into an empty screen. Let me start the first tour. It highlights the real element on the page and explains it. I can go forward, go back, skip, resume exactly where I stopped, or replay it after finishing. Restart tutorial progress clears only the tours, never workspace data.

## 6. My Work and Inbox

My Work is each person's single list: handovers addressed to me, knowledge I am asked to review, tasks assigned to me, and the cases I coordinate with their open tasks and status. The Inbox collects notifications: assignments, approvals, mentions, reminders and automation alerts. Email is optional; every notification also lives here.

## 7. People, teams and departments

People and Teams is the organisation directory. Departments, people with their title, department, manager and GitHub login, and teams. People can be added here or imported from a spreadsheet. Let me open Arjun. His page shows every ownership role he holds, the open risks that depend on him, and the continuity cases that affect him, plus a button to simulate his absence. Team and department pages show the same view for a whole group, including the department's own continuity debt.

## 8. Responsibilities and ownership

The heart of Relay is the responsibility catalogue. A responsibility is anything that must keep working, software or not. Each row shows its criticality, its primary owner and its backups. Let me open Production deployments. Stewardship shows when the record was last reviewed and by whom; owners mark it reviewed on a cadence, so stale ownership becomes visible. Then the current owners and backups, where I can end or correct an assignment with a reason. Continuity shows its risks and cases. Dependencies link it to other work and assets, such as depends on, feeds, escalates to or shares access with. Then its knowledge, the assets it stewards, and the full ownership history, which is never overwritten. This is the single source of truth that Jira, Confluence and a service catalogue each only hold a piece of.

## 9. Governed knowledge

Knowledge holds procedures, decisions, contacts and links, each tied to a responsibility. Items have stewards and review dates; anyone can confirm an item is still accurate, and stewards verify or archive it. Pages imported from Notion stay unverified until a person checks them. Let me open Deploy payments API. Relay flags a possible conflict with the old runbook, which still describes a deploy without a canary. Every edit is a version I can compare, and disputes keep their history.

## 10. Assets

Assets are the things work depends on: repositories, services, vendors, infrastructure and documents. They can be filtered by type, lifecycle, criticality, and whether anyone looks after them. The Legacy SFTP bridge, for example, has no stewarding responsibility, which Relay raises as a risk. Opening billing database shows its details, the work and knowledge linked to it, who looks after it, and the risks that reach it through its stewards.

## 11. Round 3 feature 1: Project Memory Replay

Now the first of our three Round 3 improvements, Project Memory Replay. A successor's first week is usually spent digging through old tickets. Memory Replay turns that into minutes. It answers the question every successor has: how did this work get here? Relay merges pull requests, issues, pages, decisions and ownership changes into one timeline for the responsibility. Every event is a fact with its source. I can filter by category; let me pick Incident: here is the checkout outage after a payments API release. Back to all events. Press replay and the history plays forward, event by event. I can pause and inspect any event: where it came from, how its category was derived, and which events it links to. Large histories load two hundred events at a time.

## 12. Memory Replay: AI chapters and questions

Now Explain this history. The AI groups the events into chapters on the time axis. Every chapter is labelled Inferred, because it is an interpretation, and it cites the exact events it rests on; a citation that does not exist is dropped. I can also ask the history a question: why does every payments API deploy need a canary? The answer cites the outage and the decision that introduced the canary. If the history does not record the answer, Relay says so instead of guessing.

## 13. Continuity risks

Continuity risks are raised by explainable rules, never by a model: no backup, a backup who is the same person as the owner, a critical responsibility with a single owner, team ownership without an accountable contact, or an asset nobody stewards. Let me open one. Each risk explains why it is a risk, the recommended action, and the affected responsibility. A manager can assign it, accept it with a reason, or open a case, and every decision is audited.

## 14. Insights, trends and key-person exposure

Insights is for managers and auditors, filterable by department and criticality. Continuity debt is the sum of explained components, each with its rule and points, so fixing an item lowers the debt by exactly its points. New in this round is key-person exposure: the people who are the only holder of some work, ranked by criticality. If Arjun were away tomorrow, production deployments would have nobody. Coverage, knowledge health and continuity operations follow, such as overdue tasks and the median days to close a case. Trends saves snapshots so you can see whether continuity is improving over thirty, ninety or one hundred eighty days, with every metric's definition shown. Members cannot open Insights; the server refuses it.

## 15. Round 3 feature 2: What If? simulator

From key-person exposure, one click opens our second improvement, the What If simulator. This is the moment that changes a manager's week: instead of discovering the gap after someone leaves, they see it today, while there is still time to act. It answers: if this person is unavailable, what breaks, and who should cover? I'll set Arjun as unavailable for two weeks and run it. Relay forecasts, deterministically and read-only, what changes: production deployments are left with nobody, readiness drops to fifty-five out of one hundred, and open work that falls due while he is away is listed. Every result explains why it is affected, for example, Arjun Rao is primary owner.

## 16. What If?: cover candidates

Below is Who could cover. Candidates come from recorded links: the planned recipient, an existing role, the same team or department. Each candidate is simulated with the same rules and compared with nobody stepping in. Anyone who would carry far more than the team's typical load is flagged as would be overloaded, so a manager does not pick someone already stretched. Let me simulate with Dev, the planned recipient. The gap closes and readiness rises, and a banner confirms nothing in the workspace changed. Plan a real handover opens the case form with the person already selected; starting a real case is a separate, audited step.

## 17. Continuity cases

Here is the departure case for Arjun. Relay supports onboarding, transfer, temporary coverage, departure and project handover cases. A case moves through an explicit state model: scope, plan and approve, hand over, and complete. The progress bar and the next step always tell the manager what to do now. Blockers are listed with who must resolve them. The ownership plan shows, for each responsibility, who holds it now, who receives it, and when it moves.

## 18. Inside a case

Impact shows what the case touches: assets, connected sources, open risks and knowledge, and it labels a missing source as unavailable rather than empty. Knowledge lists everything to hand over; each item can be marked handed over or noted as missing, and the whole pack downloads as Markdown. Tasks and readiness holds the work and the checks that must pass before the case can complete. People lists participants and a privacy notice, so the people involved know what Relay reads about them. Approvals records each decision against a specific plan version, and Activity keeps the status history and comments.

## 19. Analysis and handover interview

The analysis groups findings into conflicts, missing evidence, work in flight, dependencies and findings. Each one is labelled Fact, Rule, AI inference, Conflict or Missing evidence, with its sources, and a manager can confirm or dismiss it. Uncited claims are dropped, and evidence only managers may see never reaches a member. The handover interview turns gaps in the evidence into questions for the person leaving. They can answer, or say they don't know, it is not applicable, or they cannot share it. Reviewed answers can be promoted into knowledge, so tacit knowledge is captured before the person goes.

## 20. Round 3 feature 3: AI Handover Copilot

Now our third improvement, the AI Handover Copilot. Most handover documents are written in a hurry and trusted blindly. This one shows its evidence for every line, and tells you what it does not know. It writes a handover brief for one specific recipient. Brief coverage at the top shows, for every responsibility in the case, whether the brief says something about it backed by a cited source, mentions it without a source, or does not cover it, critical items first, with a link to the interview to close the gaps. The brief has fixed sections: what you now own, in-flight work, knowledge gaps and open questions, risks and conflicts, recommended first steps, and where this work came from. Every statement is labelled Fact, Rule or AI inference, and I can expand its sources.

## 21. Copilot questions

The recipient can ask questions about the handover. Let me ask: how should I deploy payments API? The answer uses only the evidence behind this brief that I may see, cites it, and points out the conflicting old runbook. Now something the evidence cannot answer: what is the AWS root password recovery process? Relay answers: not in the evidence. It never invents an answer. If the AI draft is slow or fails, the page says so honestly and offers a retry, and the rule-based brief is always usable. For a recipient, that honesty is the difference between trusting a brief and double-checking everything.

## 22. Versions, approval and acknowledgement

Every edit creates a new version that needs approval again, so a reviewer always approves exactly what the recipient will read. Compare shows the statements added and removed between versions. The recipient acknowledges a specific approved version. After acknowledging, the brief shows the recipient's next steps: their open tasks, the responsibilities they are taking over with a link to each history, the case status, and where to ask questions.

## 23. Temporary coverage

Not every change is permanent. Priya on leave is a temporary coverage case. The ownership plan shows Sara covering payments API operations and refund approvals from the start date, and Priya back in charge on her return date. Coverage can be extended or ended early, and before Priya returns Relay prepares a return briefing of everything that happened while she was away.

## 24. A complete transfer, end to end

Now a complete transfer, live. I create a new responsibility transfer case, add access reviews, and choose Leo Martins as the recipient. I submit it for approval and approve it. Then I execute the handover. Execution ends the old assignment and starts the new one in a single audited transaction, and the ownership history is preserved, never overwritten. Critical responsibilities also require separation of duties: the person who verifies completion must be someone who neither started nor approved the case.

## 25. Follow-through: did the handover take hold?

And this is new: follow-through. Approval and execution prove the plan was applied, but not that the handover worked. For each transferred responsibility Relay now checks: is the new holder recorded, has the work been reviewed or shown recorded activity since the handover, and are the handover tasks closed. It shows settled, settling in, check in after fourteen quiet days, or new holder not recorded. It measures the work, not the person, so it never becomes employee surveillance. As far as we could find, none of the catalogue, knowledge or offboarding tools we researched closes this loop. Relay does.

## 26. Integrations

Integrations connects GitHub, Linear and Notion, all read-only. The GitHub App reads repository metadata, code owners files and maintainers, never source code, and turns them into ownership suggestions that change nothing until a manager accepts them. Linear brings projects and issues and asks a person to link Linear users to directory people. Notion imports only the pages you share, into knowledge, unverified. Sync health shows each connector's last sync, failures and retries, and you can sync now or pause.

## 27. Automations and AI agents

Automations turn rules into notifications or follow-up tasks, run on a schedule or on demand, and every run is recorded. The AI agents page lists each AI capability, such as the case analyst, knowledge interviewer, handover generator, handover copilot and memory narrator, with recent runs, tokens and cost against a monthly budget. One switch turns AI off for the whole workspace; everything else keeps working.

## 28. Audit, import, members and settings

The audit log is append-only, filterable by area, person, record and date, and exportable as CSV. Import brings people, responsibilities and ownership from a CSV file with a preview before anything is written. Members invites people with a role: owner, admin, continuity manager, knowledge steward, team manager, member, auditor or guest, and permissions are enforced by the server inside every service. Settings holds the continuity policies, criticality tiers and responsibility types, the roles reference, email preferences, and data controls: what Relay reads and why, full export, retention, ownership transfer and workspace deletion, which needs the exact name typed to confirm.

## 29. Search anywhere

From anywhere, Control K opens search: jump to a person or responsibility, or start a case without leaving the page. The full search page finds responsibilities, assets, knowledge, risks and connected evidence in one list.

## 30. Why Relay

So, why Relay? Because today continuity lives in five tools and in people's heads, and it fails silently, on the day someone leaves. Relay brings it into one place and one lifecycle. Memory Replay explains the past. The What If simulator shows the future and finds the right successor before anyone has left. The Handover Copilot delivers a brief that proves every claim and admits what it does not know. And follow-through confirms the handover actually took hold. Under the hood, the database is the source of truth, AI only proposes cited drafts and never changes a record, and every workspace is isolated by Postgres row-level security, backed by nearly three hundred tests on a real database and twenty-three browser journeys. Everything I showed you is live, and the judge guide in our repository maps every claim to its code and its tests. When people move on, the work shouldn't stall. That is Relay. Thank you.
