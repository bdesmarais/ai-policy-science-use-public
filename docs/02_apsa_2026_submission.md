# APSA 2026 Submission — which version was submitted

**Short answer:** the version submitted to APSA 2026 is
[`APSA_2026_Proposal_SUBMITTED_bd_edits.docx`](source_materials/APSA_2026_Proposal_SUBMITTED_bd_edits.docx)
— **Bruce's January 13 2026 edit** of Nitheesha Nakka's draft, rewritten to **focus on the
pilot (California education press-release) data** rather than promising new work. Nitheesha
submitted it that day as an **individual paper** under the **Information Technology & Politics**
division (with **Political Methodology** as the second choice).

## How the submission came together (from the email thread)

| Date | Who | What |
|---|---|---|
| 2025-12-22 | Bruce → Nitheesha | Invites her to apply to APSA 2026 (deadline Jan 14) "with the AI paper"; attaches the Notre Dame talk slides. |
| 2025-12-24 | Nitheesha → Bruce | Agrees to apply. |
| 2026-01-06 | Bruce → Nitheesha | Sends the W.T. Grant LOI as a basis; suggests divisions **IT & Politics** and **Political Methodology**. |
| 2026-01-12 | Nitheesha → Bruce | Sends initial draft (`APSA 2026 Proposal Submission.docx/.pdf`) "bridging the AI talk and the letter of interest"; asks for help formatting the research design; notes 5,000-char / 700–1000-word limit. |
| 2026-01-13 | Bruce → Nitheesha | Returns `APSA 2026 Proposal Submission_bd_edits.docx`: *"I edited the abstract to focus on the pilot data… it alludes to results while leaving flexibility… we are proposing to present done…ish work."* |
| 2026-01-13 | Nitheesha → Bruce | *"I'll submit this today under individual paper submission"*; will designate the IT & Politics division. |
| 2026-01-13 | Bruce → Nitheesha | Confirms IT & Politics, "with methods as a second choice." |

So there were three versions in play:
1. Nitheesha's original draft — `APSA 2026 Proposal Submission.docx` / `.pdf` (in email only; not
   downloadable here — see [MISSING_MATERIALS.md](../MISSING_MATERIALS.md)).
2. **Bruce's edit — `APSA 2026 Proposal Submission_bd_edits.docx` — THE SUBMITTED VERSION** (in
   this repo).
3. (No later revision; #2 is what went in.)

## Conference / division

- **APSA 2026 Annual Meeting** (the proposal deadline was January 14 2026).
- **Submission type:** individual paper.
- **Division (1st choice):** Information Technology & Politics.
- **Division (2nd choice):** Political Methodology.
- **Submitting author:** Nitheesha Nakka.

## Full text of the submitted abstract

> **APSA 2026 Proposal Submission — Nitheesha Nakka**
>
> Political conflict increasingly centers on systems of education. Contemporary U.S. education
> policymaking involves increasingly frequent debates over social-emotional learning,
> curriculum content, school safety, and educational technology, marked by sharp partisan
> disagreement and competing claims about "what the research shows." These conflicts raise
> foundational questions for democratic governance: how can scientific evidence inform policy
> in polarized political environments where scientific authority itself is contested?
> Additionally, how might emergent technologies, including advanced large language models
> (LLMs), be used to effectively synthesize scientific evidence and make relevant research more
> accessible to legislators?
>
> This paper introduces and evaluates an AI-assisted evidence linking system that processes
> policymaking documents through a structured pipeline. Building on recent advances in large
> language models and retrieval-augmented generation (RAG), we develop an automated system that
> identifies empirical claims in policymakers' public communications, retrieves relevant
> peer-reviewed research, and evaluates the degree to which the scientific record supports,
> refutes, or is silent on those claims. The system produces concise, nonpartisan evidence
> summaries designed for time-constrained legislators and staff, lowering barriers to research
> use in policymaking.
>
> We present results from a pilot study applying this pipeline to state legislative
> communications on education policy. Our pilot corpus comprises 5,131 press releases from
> California State Assembly members, including 4,279 from Democratic legislators and 852 from
> Republican legislators. The partisan imbalance reflects the fact that approximately 75% of
> California legislators are Democrats. Our policy-to-science pipeline extracts evidentiary
> claims from policymaking documents using Google NotebookLM and then employs a web-connected
> LLM (GPT-5) to collect claim-relevant scientific references. This approach has proven
> effective in related work examining claims in AI policy press releases, where we observed
> substantial scientific reference activity across partisan lines, with top publication venues
> including arXiv, Science, PNAS, and Nature.
>
> Keyword-based filtering identified 611 education-related press releases (11.9% of the corpus).
> Notably, Democratic legislators devoted a significantly higher proportion of their
> communications to education topics (13.1%) compared to Republican legislators (5.9%). Analysis
> of polarized topic coverage reveals substantial partisan differences in policy attention.
> Democratic legislators produced 80 press releases addressing social-emotional learning
> compared to just 1 from Republican legislators. Similarly, school safety communications were
> considerably more prevalent among Democrats (n=38) compared to Republicans (n=4). These
> asymmetries suggest that partisan polarization structures not only the positions legislators
> take but also which education topics receive attention in legislative communications.
>
> The paper proceeds in two stages. First, we analyze this pilot corpus of California state
> legislative press releases on education policy to document how policymakers invoke scientific
> evidence in public communication and how these practices vary by party affiliation and policy
> subdomain. We examine patterns in the types of scientific claims made, the frequency of
> explicit evidence citation, and the substantive domains of cited research. Second, we validate
> the AI pipeline by comparing automated claim-evidence assessments to human expert coding
> across a stratified sample of policy claims, demonstrating that AI-assisted evidence linking
> can achieve reliable performance in politically charged issue areas. This validation work
> establishes the methodological foundation for future scaled applications of the pipeline.
>
> Preliminary findings from California reveal substantial partisan asymmetries in both attention
> to education topics and the types of scientific claims invoked in these press releases,
> suggesting that evidence use itself is structured by polarization. Democrats more frequently
> reference research on student mental health, equity, and developmental outcomes, while
> Republican communications more often invoke research on school safety, parental rights, and
> educational accountability. These patterns raise important questions about whether partisan
> differences in evidence use reflect genuine disagreement about which research is relevant or
> strategic selection of evidence to support predetermined policy positions.
>
> This paper bridges political communication, public policy, and science-and-technology studies.
> We argue that AI systems can reshape, not replace, the conditions under which evidence enters
> political discourse by creating shared reference points across partisan divides. Importantly,
> we do not assume that evidence will depolarize politics; instead, we evaluate whether
> AI-mediated evidence assessment can support more transparent policymaking by making the
> evidentiary basis of policy claims explicit and accessible. In practice, legislators may
> resist evidence that challenges partisan positions, yet they also face constituent and media
> pressure to justify policy stances. Our design provides an empirical foundation for
> understanding these dynamics in the education policy domain.
>
> Substantively, this paper provides the first systematic analysis of how state legislators
> communicate about scientific evidence in education policy, a domain characterized by intense
> partisan conflict and consequential policy stakes. Methodologically, it demonstrates how AI
> tools can be integrated into rigorous political science research while maintaining
> transparency about the capabilities and limitations of automated evidence assessment.
> Practically, it offers a realistic framework for understanding and potentially improving
> evidence use in democratic institutions that must function despite partisan disagreement.

## Note

The submitted abstract pivoted the *showcased domain* to **education** (to align with the
W.T. Grant angle and APSA's "democracy under crisis" theme), but the **method and the AI-policy
findings remain the backbone** ("this approach has proven effective in related work examining
claims in AI policy press releases"). The paper as proposed promises (a) a descriptive analysis
of the CA education corpus and (b) a human-coding **validation** of the pipeline — which is
precisely the next concrete deliverable for reviving the project.
