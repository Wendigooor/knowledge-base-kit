# WHY.md Review: GLM-5.1

1. **Is the problem statement strong enough to justify building KBK?**

**No. The *pain* is real, but the *justification* is weak.**

You have accurately described a universally felt pain in enterprise engineering: knowledge rot, context scattering, and the onboarding tax. However, you are making a classic product mistake: you are pointing at a cultural/behavioral problem ("nobody updates Confluence") and proposing a technological solution ("a new database"). 

If your system analysts and developers don't update Confluence, *they will not update KBK either*, regardless of how good the semantic search is. The document claims KBK solves this via "Auto-update by LLM," but this is a massive leap of faith. How does the LLM know a decision was made? How does it know a Slack conversation resulted in an architectural change? It doesn't, unless a human triggers it or you build incredibly complex integrations. 

The problem statement justifies the need for *better documentation*, but it does not justify building a complex, custom, dual-storage (ChromaDB + Git) internal tool. You haven't proven why forcing better discipline in Confluence (or a Git-based Markdown wiki) coupled with an existing RAG tool wouldn't solve 80% of this problem for 10% of the effort.

2. **What's the weakest argument in this document?**

**The assumption that "Auto-update" (requirement #2) actually works and produces trustworthy data.**

You state that KBK is "обновляемо LLM — агенты могут добавлять и обновлять записи. Автоматически, по крону, без человека." This is the crux of your differentiation, and it is incredibly fragile. 

LLMs hallucinate. They lack the business context to know *why* a decision was made (which is the most valuable part of an ADR). If an LLM automatically updates a knowledge base "without a human," you immediately create a trust deficit. When an architect reads an ADR, they need to know a *person* made that decision for a specific reason. If the knowledge base becomes a mix of human-authored facts and LLM-generated summaries, it becomes untrustworthy. 

Furthermore, your comparison table claims Confluence and Notion have "❌ Auto-update." This is false. Both have robust APIs and hundreds of integrations that auto-create and update pages from Jira, GitHub, etc. Your "auto-update" is not a unique differentiator; your differentiator is *LLM-driven* auto-update, which is actually a liability unless heavily gated by human review.

3. **What's the single most important thing to change?**

**Narrow your target audience to a single "beachhead" persona and define the exact, specific workflow that gets them value on Day 1.**

Right now, you have 6 different personas (SA, Architect, Dev, QA, PM, New Hire) doing 6 different things. This means you are designing a Swiss Army knife when you actually need a scalpel. A tool built for everyone will satisfy no one. 

You need to pick *one* persona, *one* use case, and solve it flawlessly. For example:
*   **The Architect & ADRs:** Make KBK the absolute best place to write, store, and query Architectural Decision Records. 
*   **The New Hire & Onboarding:** Make KBK the only place a new dev needs to go to understand a service.

Once you pick that single workflow, you must define the **"Killer Trigger."** Documentation is never updated because it requires proactive effort. How does KBK get data *without* someone having to remember to write it? Does it integrate with GitHub PRs? Does it listen to specific Slack channels? Does it parse Jira tickets on status change? 

Stop selling "a database of context." Start selling a specific, automated workflow that solves a bleeding-neck problem for one specific role. If you can't define that workflow, KBK will just become another Confluence that nobody updates.