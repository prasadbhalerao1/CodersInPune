// The narrated tour, one beat per sentence or two. Each beat is [text, actions?]. A ^ marks
// the word on which the beat's actions start, so the pointer lands as the word is spoken.
// Helpers come from record.mjs; everything is clicked through the visible interface.
export default (h) => {
  const {
    page, pause, settle, click, type, hover, scroll, scrollToTop, browse, link, button,
    heading, sidebar, caseTab, subnav, background, ready, copilot, ask,
  } = h;
  const sampleReady = () => page.waitForURL(/\/w\/[0-9a-f-]{36}$/, { timeout: 120_000 });

  return [
    ["Relay", [
      ["Hello everyone, we are Team Midnight Ciphers, and we built Relay: an AI-powered organisational continuity platform designed to prevent critical knowledge from leaving with people.",
        async () => { await pause(1200); await hover(page.getByRole("heading", { level: 1 }), 1800); }],
      ["Think about what happens when someone who owns an important project, system or responsibility suddenly leaves. Their code might still exist. Their documents might still exist. But the reasoning behind decisions, unfinished work, hidden dependencies and operational knowledge are often scattered across different tools, or exist only in that person's experience.",
        () => scroll(380, 60)],
      ["Relay solves this by connecting authorised project information, reconstructing operational context, identifying risks, and preparing a verifiable handover, so the next person can continue the work with confidence. Let me show you how it works.",
        () => scrollToTop()],
    ]],
    ["Real sign-in", [
      ["Relay is a real multi-tenant product, so let's sign in properly. For judges, the home page has a sign-in card with one account per role. I'll click ^Sign in as Owner. This is a genuine WorkOS sign-in: the server authenticates the account and sets an encrypted session cookie. There is no demo mode and no bypass.",
        async () => {
          await click(link("Sign in as Owner"), 800);
          background(page.waitForURL(/\/workspaces/, { timeout: 120_000 }).then(settle));
        }],
      ["Signing in gives you an identity, but no data. Access to a company's records comes only from membership of its workspace, and the server never trusts the browser to say which workspace it is in.",
        () => ready()],
      ["This is the Workspaces page. The Owner account is a member of Northwind Labs, our judges' sample. To keep that shared space clean, I'll click ^Create sample workspace and get a private copy, built right now: eight people, seven responsibilities, a year of GitHub, Linear and Notion history, and an engineer, Arjun Rao, who is leaving.",
        async () => {
          const existing = () => click(page.getByRole("link", { name: /\(sample\)/ }).first(), 600).then(sampleReady);
          // WALK_REUSE_SAMPLE rehearses on an existing sample (creating one is limited per day).
          if (process.env.WALK_REUSE_SAMPLE) return background(existing().then(settle));
          await click(button("Create sample workspace"), 600);
          background(sampleReady().catch(existing).then(settle));
        }],
      ["While it builds, one decision we made on day one. Every company's data sits in the same Postgres database, isolated by forced row-level security. The app connects as a restricted role that cannot bypass it, so even a buggy query cannot read another tenant. Our test suite attacks exactly that boundary.",
        () => ready()],
    ]],
    ["Overview", [
      ["We land on the Overview. At the top, Relay tells me a handover is waiting for me: in this sample, I'm one of the people taking over Arjun's work.",
        async () => { await settle(); await hover(page.getByText("A handover is waiting for you"), 1800); }],
      ["Below, ^continuity health: how many responsibilities have both an owner and cover. Every number in Relay has an information icon that shows exactly how it was calculated, so nobody has to trust a score blindly.",
        async () => { await hover(page.getByRole("region", { name: "Continuity health" }), 1200); await hover(page.getByRole("button", { name: "How continuity debt works" }), 1500); }],
      ["^Continuity debt sums the unresolved risks, weighted by severity, and the cards underneath count active responsibilities, work with no primary owner, critical work with no backup, and open risks.",
        () => browse(2, 300)],
      ["The setup checklist and guided tours adapt to what the workspace already has. A brand-new company is guided through adding people, responsibilities and connections; this one is already set up.",
        () => scrollToTop()],
    ]],
    ["My Work and Inbox", [
      ["^My Work brings together everything waiting on me: tasks assigned to me, approvals, knowledge to review, and the handovers where I'm the incoming owner.",
        () => sidebar("My Work")],
      ["Relay is useful only if nothing falls through the cracks, so every action that needs a person surfaces here, and as a notification in the ^Inbox, with email for the things that matter.",
        async () => { await browse(2, 260); await sidebar("Inbox"); }],
    ]],
    ["Responsibilities", [
      ["Now the foundation. ^Responsibilities. Most tools organise around tasks or people. A task finishes, but an operational responsibility, like production deployments or month-end close, continues. So Relay models the responsibility itself.",
        () => sidebar("Responsibilities")],
      ["Each has a criticality, a primary owner, backups, and a review cadence. I can filter by criticality, department or missing backup. Notice Production deployments: critical, and no backup.",
        async () => { await hover(page.getByRole("row", { name: /^Production deployments/ }).getByRole("cell", { name: "Critical" }), 1200); }],
      ["I'll open ^Production deployments.",
        () => click(page.getByRole("link", { name: "Production deployments", exact: true }).first(), 1500)],
      ["Here are the current owners, assigned with effective dates. A transfer ends one period and starts another, so ownership history is never overwritten. That history is what lets us later replay how the work evolved.",
        () => browse(2, 280)],
      ["Further down: the knowledge attached to this responsibility, the assets it looks after, and its dependencies on other work. Those dependencies matter later, when we simulate an absence.",
        () => browse(3, 300)],
    ]],
    ["People and teams", [
      ["^People and Teams. The directory holds people, teams and departments, imported from CSV or matched from GitHub and Linear identities.",
        () => sidebar("People & Teams")],
      ["I'll open ^Arjun Rao. His profile shows everything he holds, and a direct link to ask: what if Arjun were unavailable? We'll come back to that.",
        () => click(page.getByRole("link", { name: "Arjun Rao", exact: true }).first(), 1500)],
      ["One idea runs through the whole product: a named backup is not the same as a capable backup. Someone listed as backup who has never documented or touched the work is a risk on paper. Relay shows the difference, and I'll prove it in the expertise map.",
        () => browse(2, 280)],
    ]],
    ["Assets and knowledge", [
      ["^Assets are the systems, repositories and vendors behind the work, each linked to the responsibilities that look after it.",
        () => sidebar("Assets")],
      ["^Knowledge holds runbooks, procedures and decisions. Each item has a steward, versions, a review date and a classification. AI can propose knowledge, but it never becomes verified organisational truth until a person reviews it.",
        () => sidebar("Knowledge")],
      ["At the top, Relay flags code drift: knowledge whose code changed after it was last reviewed. Here, pull requests were merged into the deploy pipeline after the old runbook was checked, so that runbook may now be wrong.",
        async () => { await hover(page.getByText(/Code changed since review/).first(), 2000); }],
      ["That matters, because a confident, out-of-date runbook is worse than none at all.",
        () => browse(2, 300)],
    ]],
    ["Integrations", [
      ["Where does the evidence come from? ^Integrations. One thing to be clear about: this is a sample workspace, so you can try every feature without connecting your own tools. Relay itself runs on real GitHub, Linear, Notion and Slack, through exactly the same code.",
        () => sidebar("Integrations")],
      ["GitHub connects as a GitHub App, read-only. Relay reads repositories, pull requests, issues, teams and code owners, but never source code. Webhooks are signature-checked and de-duplicated, and sync resumes from a checkpoint.",
        () => browse(2, 260)],
      ["To connect a real organisation, I click ^Add organisation, and GitHub's own install screen opens. The organisation's admin signs in there and chooses which repositories Relay may read.",
        async () => { await scrollToTop(); await click(button(/Add organisation|Connect GitHub/), 3500); }],
      ["I won't install it on camera; I'll come back to Relay.",
        async () => { await page.goBack().catch(() => {}); await settle(); await pause(800); }],
      ["^Suggestions match GitHub people and code owners to Relay's directory, and propose owners. Nothing merges without approval, and none are waiting now.",
        () => subnav("GitHub", "Suggestions")],
      ["^People and ^Teams show the matched identities and GitHub teams. ^Signals flag where declared ownership and recent GitHub activity disagree. Here, none.",
        async (cue) => { await subnav("GitHub", "People"); await cue(1); await subnav("GitHub", "Teams"); await cue(2); await subnav("GitHub", "Signals"); }],
      ["^Linear and ^Notion connect by OAuth the same way. Every source keeps its provenance, so anything Relay shows can be traced back to the record it came from.",
        async (cue) => { await subnav("Integrations", "Linear"); await cue(1); await subnav("Integrations", "Notion"); }],
      ["^Slack takes an encrypted webhook, so meeting summaries and handover updates can be posted to a channel.",
        () => subnav("Integrations", "Slack")],
      ["^Health shows each connection's sync runs and errors in plain words. Here, Linear is flagged as stale because it hasn't synced in the last day, and a connection that loses access gets a reconnect link. Integration secrets are encrypted at rest and never shown back.",
        () => subnav("Integrations", "Health")],
    ]],
    ["Project Memory Replay", [
      ["Now the first of our three Round 2 commitments: Project Memory Replay. A new owner doesn't just need the current state. They need to know how the work got here. I'll go back to ^Responsibilities.",
        () => sidebar("Responsibilities")],
      ["Open ^Production deployments, and click ^Memory replay.",
        async (cue) => { await click(page.getByRole("link", { name: "Production deployments", exact: true }).first(), 1200); await cue(1); await click(link("Memory replay"), 1500); }],
      ["Relay rebuilds this history from the records every time I open it: ownership periods, pull requests with their commits, GitHub and Linear issues, incidents, recorded decisions and Notion edits, grouped by month.",
        () => browse(2, 260)],
      ["Each event has a category, like bug fix, incident or documentation, and Relay shows the rule that set it. I'll filter to ^incidents only.",
        async () => { await scrollToTop(); await click(page.getByRole("group", { name: "Filter by category" }).getByRole("button", { name: /Incident/ }), 1500); }],
      ["Back to ^all. I can also filter by source, person and date range, and search. The filters live in the address, so I can send a colleague exactly this view.",
        () => click(page.getByRole("group", { name: "Filter by category" }).getByRole("button", { name: /^All/ }), 1200)],
      ["Now ^Replay history. Relay plays the project forward from its first event, so you watch the work evolve.",
        () => click(button("Replay history"), 400)],
      ["Ownership arrives, the canary stage is added, an outage hits checkout, promotion is blocked on canary errors, and the rollback procedure is written down.",
        () => pause(1500)],
      ["Let me ^inspect an event. Every event is labelled Fact: its date and source come straight from the record. The inspector shows where it was read from, why it got its category, and which part of the history it's in.",
        async () => { await click(button("Inspect").first(), 1200); await hover(page.getByRole("region", { name: "Event details" }), 1500); }],
      ["On the right, ^Related work. Records that reference each other become one thread: an issue, the pull request that fixes it, the commits that mention it. We join records only on explicit references, never on similar titles or nearby dates, because a guessed link in someone's history would mislead the next owner.",
        async () => { const r = page.getByRole("region", { name: "Related work" }); await hover(r, 2000); }],
      ["Now the AI layer. I'll click ^Explain this history. Gemini reads only the events this viewer is allowed to see, and writes chapters: what happened, why it mattered, and how events connect.",
        async () => {
          const explain = button("Explain this history");
          if (await explain.isVisible().catch(() => false)) await click(explain, 600);
          background(page.getByText(/^Inferred/).first().waitFor({ timeout: 90_000 }));
        }],
      ["Every chapter must cite the events it rests on, or it is dropped. And chapters are labelled Inferred, with a confidence level, so a judge or a new owner can always tell a recorded fact from an interpretation.",
        () => ready()],
      ["The reading is stored per viewer, and Relay says when newer events have arrived since it was written, so a stale explanation never passes as current.",
        () => browse(2, 260)],
      ["I can also ask the history a question. I'll type: why does every payments deploy need a canary?",
        async () => {
          await type(page.getByLabel("Your question"), "Why does every payments-api deploy need a canary?");
          await click(button("Ask"), 500);
          background(page.getByText(/From the history|Not in the history|Search results, not an answer/).first().waitFor({ timeout: 90_000 }));
        }],
      ["The answer cites the outage and the change that followed it. If the history doesn't contain the reason, Relay says so instead of guessing. That is the whole point: understand how the project reached this state, not just what it looks like today.",
        async () => { await ready(); await hover(page.getByText(/From the history|Not in the history|Search results, not an answer/).first(), 2500); await browse(1, 200); }],
    ]],
    ["What If? simulator", [
      ["Second commitment: the What If? continuity simulator. Managers need to know what would break before someone leaves, not after. I'll open the ^What-if simulator.",
        () => sidebar("What-if simulator")],
      ["I'll pick ^Arjun Rao, set him away for ^two weeks, and click ^Run simulation.",
        async (cue) => {
          const person = page.locator('select[name="person"]');
          await click(person, 300);
          const arjun = await person.locator("option").filter({ hasText: "Arjun" }).first().getAttribute("value");
          await person.selectOption(arjun);
          await cue(1);
          await page.getByLabel("is unavailable for").selectOption({ label: "2 weeks" }).catch(() => {});
          await cue(2);
          await click(button("Run simulation"), 1500);
        }],
      ["Relay recomputes everything Arjun holds, in memory. ^Readiness is a plain formula, shown row by row: does someone still cover the work, is there usable knowledge, is a second holder left, weighted by criticality. No AI score.",
        () => hover(page.getByText(/Continuity readiness/).first(), 1500)],
      ["^What changes: Production deployments is left with nobody. Platform on-call would rest on one person. Each row says why it's affected, and which repository it touches.",
        async () => { await hover(page.getByText("What changes").first(), 900); await click(page.getByText("Why it is affected").first(), 1200); }],
      ["On the right, the newly exposed gaps: production deployments with no cover, and platform on-call resting on Leo Martins alone. Below that, ^downstream impact follows the recorded dependency chain, so a manager sees the second-order damage too.",
        async () => { await hover(page.getByRole("heading", { name: "Downstream impact" }), 2000); }],
      ["Now, who could cover? Relay ranks candidates by recorded links to this work, and simulates each one against nobody stepping in. Anyone who would end up overloaded is flagged.",
        async () => { await hover(heading("Who could cover?"), 1800); }],
      ["I'll ^pin this scenario, then ^simulate with Dev.",
        async (cue) => { await click(link(/Pin to compare/).first(), 1200); await cue(1); await click(link("Simulate with Dev"), 1800); }],
      ["With Dev covering, nothing critical is left uncovered and readiness rises. I'll pin this one too, and the comparison shows both scenarios side by side.",
        async () => { await click(link(/Pin to compare/).first(), 1500); await browse(2, 300); }],
      ["The key design decision: this is completely read-only. A test attaches a database listener and fails if a simulation writes anything. Acting on a scenario is a separate step: Plan a real handover opens an audited case.",
        () => scrollToTop()],
    ]],
    ["The handover case", [
      ["Now the heart of Relay: the continuity case, where ownership actually moves. I'll open ^Cases, and Arjun's departure.",
        async () => { await sidebar("Cases"); await click(page.getByRole("link", { name: /Arjun Rao is leaving Platform/ }).first(), 1500); }],
      ["A case moves through stages: scope, plan and approve, hand over, then complete. The server enforces every transition; the interface cannot skip one.",
        () => hover(page.getByText(/Scope/).first(), 1500)],
      ["This case is blocked: Dev doesn't have production deploy access yet. A blocker has an owner and an escalation time, and the case can't advance until it's resolved.",
        () => hover(page.getByText(/production deploy access/).first(), 1800)],
      ["The ownership plan lists each responsibility, who holds it now and who receives it, with handover notes. Each incoming owner must accept their responsibility. As coordinator, I can ^record Dev's acceptance after confirming it with him.",
        async () => { await browse(1, 260); const rec = button(/Record acceptance for Dev/); if (await rec.isVisible().catch(() => false)) await click(rec, 1500); }],
      ["Why acceptance? Because sending a document is not the same as transferring responsibility. The case refuses to complete while any task is open, a readiness check is unmet, or an incoming owner hasn't accepted.",
        () => browse(1, 260)],
      ["^Impact shows what this case carries: the assets, open work in Relay, GitHub and Linear, and the knowledge behind each responsibility in scope.",
        () => caseTab("Impact")],
      ["^Knowledge is the knowledge handover: what the recipient needs to know, what was handed over, and what is still missing.",
        () => caseTab("Knowledge")],
      ["^People lists everyone involved in this case and their part in it.",
        () => caseTab("People")],
      ["^Tasks and readiness: the concrete work of the handover, each with an owner and a due date, plus the readiness checks a reviewer must sign off.",
        () => caseTab("Tasks & readiness")],
      ["^Approvals use plan versions and separation of duties: on a critical case, the person who prepared the plan cannot approve it.",
        () => caseTab("Approvals")],
      ["^Activity is the case's full history, and every change is also written to the append-only audit log in the same database transaction.",
        () => caseTab("Activity")],
    ]],
    ["Autopilot and the interview", [
      ["^Analysis is where AI helps prepare the handover. Handover Autopilot runs the whole analysis in one click, and you watch every step.",
        () => caseTab("Analysis")],
      ["I'll click ^Run Autopilot. It reads the case, gathers the evidence I'm allowed to see, checks the continuity rules, then runs four AI reviewers, each shown with its tool calls.",
        async () => {
          const run = button(/Run Autopilot/);
          if (await run.isVisible().catch(() => false)) await click(run, 800);
          background(page.getByText(/proposals? (waiting|to review)|Autopilot finished|Done/i).first().waitFor({ timeout: 150_000 }));
        }],
      ["Watch the tool calls: the models only have two tools, search evidence and get evidence. They can read; they cannot write. Nothing they produce changes a record until a person accepts it.",
        () => pause(6000)],
      ["Evidence arrives marked as untrusted data, so an instruction hidden inside a document is treated as text, not a command. Our safety evaluation includes exactly that attack, along with thirty other labelled cases, and runs on every push.",
        () => pause(6000)],
      ["Every claim a model makes must cite evidence from the pool it was given. A citation to something it was never given is removed, and the run is flagged for review.",
        () => ready()],
      ["The result is a set of proposals: tasks, knowledge, readiness checks. Each is accepted or rejected by a person, with a reason, and that decision is audited.",
        () => browse(2, 300)],
      ["^Interview captures what no system holds: the departing owner's own knowledge. AI asks about the gaps the evidence can't explain, and Arjun can answer by voice. Reviewed answers feed the handover brief.",
        () => caseTab("Interview")],
    ]],
    ["AI Handover Copilot", [
      ["Now our third commitment: the AI Handover Copilot. ^Capsules holds one brief per recipient. I'll open mine.",
        async () => { await caseTab("Capsules"); await click(page.getByRole("link", { name: /^For / }).first(), 1800); }],
      ["The brief always has the same sections: what you now own, in-flight work, decisions already made, knowledge gaps and open questions, risks and conflicts, and recommended first steps.",
        () => browse(2, 300)],
      ["Every statement carries a label, fact, rule or AI inference, and its sources. ^Click a source and it opens in a side panel, so I can check the evidence without leaving the brief.",
        async () => { await click(page.locator("summary").filter({ hasText: /^\d+ sources?:/ }).first(), 900); await click(page.getByRole("button", { name: /^Inspect evidence/ }).first(), 2600); await click(button("Close evidence"), 600); }],
      ["When two sources disagree, Relay shows both, side by side, instead of choosing one. And when a source changes after the brief was written, the statement is marked, and Compare shows exactly what changed between versions.",
        () => browse(1, 280)],
      ["At the top, brief coverage: which responsibilities in scope are backed by evidence, mentioned without a source, or not covered at all. And evidence strength, Strong, Partial or Weak, with its working shown.",
        async () => { await scrollToTop(); await hover(page.getByRole("heading", { name: "Brief coverage" }), 1800); }],
      ["Now the Copilot itself. I'll ask: ^How should I deploy payments API?",
        () => ask("How should I deploy payments-api?")],
      ["What makes this different from a generic chatbot: it answers only from the evidence behind this handover, filtered to what I'm allowed to see before any model receives it. Restricted material can't leak into an answer.",
        () => ready()],
      ["The answer streams with its sources, and it points out that an older runbook says the opposite. Every claim cites the evidence it came from.",
        async () => { await hover(copilot().getByRole("article").last(), 2200); }],
      ["Now a question it shouldn't be able to answer. ^What is the zebra quokka escalation code?",
        () => ask("What is the zebra quokka escalation code?")],
      ["A confident invented answer would be the worst outcome in a real handover, so Relay refuses to make one up.",
        () => ready()],
      ["Not in the evidence, with the closest sources to check. An answer that cites nothing is never shown as an answer. With AI switched off or over budget, the panel says so and shows a labelled keyword search instead.",
        async () => { await hover(copilot().getByRole("article").last(), 2000); }],
      ["Follow-up suggestions come from the brief's own open questions, and Who to ask lists the current holders, backups and previous owners from the ownership records.",
        () => browse(2, 300)],
      ["And handover rehearsal: practice questions drawn from the brief's evidence, graded by rules against the source, so the new owner can check what they really understood before taking over.",
        () => browse(2, 300)],
      ["Finally, I ^acknowledge the brief. Acknowledgement is per version: if the brief is edited later, it needs approval and acknowledgement again.",
        async () => { await scrollToTop(); const ack = button(/Acknowledge/); if (await ack.isVisible().catch(() => false)) await click(ack, 1500); }],
    ]],
    ["30/60/90 and follow-through", [
      ["Back in the case, the ^30/60/90 plan gives the successor a first-ninety-days plan: shadow on critical work, take the lead, document what's undocumented, train a backup. Each step explains why, and any step becomes a task.",
        async () => { await page.goBack().catch(() => {}); await settle(); await caseTab("30/60/90 plan"); }],
      ["After a transfer completes, follow-through checks whether each responsibility actually took hold: is the new holder doing the work? It measures the work, not the person.",
        () => browse(2, 280)],
    ]],
    ["Meetings and decisions", [
      ["Not all context lives in tickets. ^Meetings: paste notes or a transcript, and Relay extracts decisions, actions with owners and due dates, open questions and risks, each linked to the line it came from.",
        () => sidebar("Meetings")],
      ["I'll open the ^Arjun handover kickoff.",
        () => click(page.getByRole("link", { name: /Arjun handover/ }).first(), 1500)],
      ["Accepting a decision records it as decision knowledge. Accepting an action creates a task on the case, assigned to the person named. Summaries can be posted to Slack through an encrypted webhook. With AI off, rules still do the extraction.",
        () => browse(2, 300)],
      ["The ^Decision log brings every decision into one timeline, recorded, from meetings, or reconstructed by analysis, each linked to its source.",
        () => sidebar("Decision log")],
    ]],
    ["Ask Relay", [
      ["^Ask Relay answers questions across the whole workspace. I'll ask: ^who is the backup for refund approvals?",
        async (cue) => {
          await sidebar("Ask Relay");
          await cue(1);
          const box = page.getByPlaceholder(/Ask about owners/);
          await type(box, "Who is the backup for refund approvals?");
          await page.keyboard.press("Enter");
          background(pause(15_000));
        }],
      ["It searches only records I may open, answers as it streams, cites every record it used, and says Not in the records rather than guessing.",
        () => ready()],
    ]],
    ["Risk and insight", [
      ["^Risks are generated by rules, not by AI: no owner, no backup, a single holder, stale knowledge. Each shows the rule that raised it, and can be accepted with a reason or resolved. Unresolved risk becomes an actionable backlog.",
        () => sidebar("Risks")],
      ["The ^Expertise map compares responsibilities against people, fragile work first, and separates a backup on paper from a capable backup who has actually documented the work.",
        () => sidebar("Expertise map")],
      ["^Insights shows continuity debt by component, and key-person exposure: the people who are the only holder of critical work, each with a link to simulate their absence.",
        async () => { await sidebar("Insights"); await browse(2, 300); }],
    ]],
    ["Trust and administration", [
      ["Relay has eight roles from one deny-by-default permission registry. With ^Try Relay as, I can preview the workspace as a member.",
        async () => {
          const role = page.getByRole("combobox", { name: /Try Relay as/ }).or(page.locator("select").filter({ hasText: "Owner" })).first();
          await click(role, 300);
          await role.selectOption({ label: /Member/ }).catch(async () => {
            const v = await role.locator("option").filter({ hasText: "Member" }).first().getAttribute("value");
            await role.selectOption(v);
          });
          await settle();
        }],
      ["As a member, admin pages leave the sidebar, and this one is closed to me. The server refuses it too; every service checks permissions itself. I'll ^switch back to Owner.",
        () => click(button(/Switch back to Owner/), 1500)],
      ["^Members shows who has access, their role and status. Invitations go by email.",
        () => sidebar("Members")],
      ["^Automations schedule continuity checks, like critical work without a backup. ^AI agents shows each capability, the providers, and every run's tokens and cost against a monthly budget, with a kill switch.",
        async (cue) => { await sidebar("Automations"); await cue(1); await sidebar("AI agents"); }],
      ["^Import brings people, teams and responsibilities in from a CSV file, with a preview before anything is written.",
        () => sidebar("Import")],
      ["^Settings. Policies are the continuity rules: whether critical work must have a backup, and how often knowledge must be reviewed. Every change to them is audited.",
        () => sidebar("Settings")],
      ["^Types and tiers define what each criticality requires. ^Roles and access lists every role and exactly what it allows.",
        async (cue) => { await subnav("Settings", "Types & tiers"); await cue(1); await subnav("Settings", "Roles & access"); }],
      ["^Data and privacy states what Relay reads from each source, and why, with a full JSON export. ^Notifications choose what also arrives by email.",
        async (cue) => { await subnav("Settings", "Data & privacy"); await browse(1, 260); await cue(1); await subnav("Settings", "Notifications"); }],
      ["And the append-only ^audit log records every change, who made it and when, without storing any content or secrets.",
        () => sidebar("Audit log")],
    ]],
    ["Learning Relay", [
      ["A new user shouldn't need a manual. ^Learn Relay offers eight guided tours that unlock as the workspace grows, and spotlight the real interface. They can be skipped, resumed or replayed.",
        () => sidebar("Learn Relay")],
      ["And Control K searches everything from anywhere.",
        async () => { await page.keyboard.press("Control+K"); await pause(1800); await page.keyboard.press("Escape"); }],
    ]],
    ["Engineering", [
      ["A few words on how it's built. A Next.js web app, one FastAPI service, a background worker and one Postgres database, as a modular monolith. Background work goes through a transactional outbox, so it commits or rolls back with the change that caused it.",
        () => sidebar("Overview")],
      ["Relay is tested on a real database as the restricted app role: three hundred and seventy-one backend tests, a thirty-one case AI safety evaluation, and browser journeys that start from the landing page, all running on every push.",
        () => browse(1, 260)],
      ["And sessions are real. I'll ^sign out, and the protected pages are closed to me again.",
        async () => { await click(button("Sign out"), 1500); await settle(); }],
    ]],
    ["Closing", [
      ["That is Relay. We started with a simple problem: when people leave, critical knowledge should not leave with them.",
        () => pause(1500)],
      ["By connecting authorised organisational information, understanding responsibilities, reconstructing project history and preparing evidence-backed handovers, Relay helps organisations maintain continuity, rather than rediscover everything after someone leaves.",
        () => pause(1500)],
      ["Our goal is not another AI summary. It is to make sure the next person can understand the work, take ownership and continue it with confidence. We are Team Midnight Ciphers, and thank you for your time.",
        () => pause(2500)],
    ]],
  ];
};
