# KBK v0.3 — Stakeholder Demo Script (5 min)

> 3 tracks. 5 minutes. No live demos of brittle parts.
> Reviewed by GLM-5.1 + Kimi K2.6.

---

## Setup (do once)

```bash
kbk init
kbk sync              # full sync
kbk build-showcase    # generate showcase
```

Pre-record Track 2 as a screen capture video.

---

## Track 1: Why should I care? (2 min — live)

**Goal:** Show the output first. Make them want to know how it works.

**Script:**

1. Open the Showcase page.
   ```
   "This is KBK Showcase — an auto-generated index of everything we've approved and documented.
   Every document has a summary, tags, and a link back to the original Confluence page."
   ```

2. Expand a collection (e.g. `arch`).
   ```
   "These are our architecture decisions. Organized, searchable, up to date."
   ```

3. Open a document — read summary — click source link.
   ```
   "One click back to the original. KBK doesn't replace Confluence. It makes Confluence discoverable."
   ```

4. Ask an agent: "How do I deploy the payment service?"
   ```
   "Behind the scenes, the agent called KBK through MCP — found the deployment guide,
   read the summary, and answered with a link to the source. No hallucination."
   ```

---

## Track 2: How does it work? (2 min — pre-recorded video)

**Goal:** Show the plumbing without risking a live failure.

**Video script (narrate over recording):**

1. **Source → Index:**
   ```
   "Here's a Confluence page. I run 'kbk sync'.
   KBK pulls it through the allowlist, diffs it, cleans the HTML,
   asks the LLM for a summary, chunks it, and embeds it into ChromaDB.
   All in one command."
   ```

2. **Change propagation:**
   ```
   "I edit the page. Run 'kbk sync' again.
   StateTracker detects the SHA-256 changed — only this doc re-indexes.
   Everything else is skipped. Cost of this sync: near zero."
   ```

3. **Agent retrieval:**
   ```
   "I ask the agent: 'How do I roll back a deployment?'
   It calls search_knowledge, gets the runbook, reads the summary,
   and answers with a source link. Every claim has a trace back to Confluence."
   ```

---

## Track 3: What's next? (1 min — live)

**Goal:** Roadmap clarity without promising the moon.

**Script:**

```
"Track 1 is what works today. Track 2 is how it works.
Here's where we're going:

Confluence is live. Fully indexed, searchable, agent-ready.
Jira and GitLab follow the same pipeline — the connector contract is defined,
so adding a source doesn't require re-architecting.
AuthZ at retrieval is in progress: every chunk carries an access_group,
and the API enforces it before returning results.
And every retrieval has a trace ID — if something goes wrong,
we can trace agent → API → ChromaDB → source in one query.

That's the KBK v0.3 plan. Any questions on what you've seen?"
```

---

## CLI Reference

```bash
kbk status              # what's indexed
kbk sync --dry-run      # preview cost
kbk sync                # full sync
kbk search "query"      # search
kbk search "query" --collection runbooks  # scoped
kbk list-collections    # list collections
kbk build-showcase      # human-readable view
kbk serve               # MCP server for agents
```

## Success Criteria

After the demo, stakeholders should be able to answer:

1. "What does KBK do?" → Indexes enterprise knowledge, makes it searchable by humans and agents
2. "Where does knowledge come from?" → Confluence (Jira/GitLab next)
3. "How does an agent use it?" → MCP → search → summary → source link
4. "Can agents see everything?" → No — access_group is enforced at retrieval
5. "What's the roadmap?" → Confluence now, Jira next, GitLab later
