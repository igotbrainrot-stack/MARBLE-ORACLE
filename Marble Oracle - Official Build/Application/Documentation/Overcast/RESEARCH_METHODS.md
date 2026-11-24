# OVERCAST research and methods (formerly SIGNAL)


**Research:** 22 November 2026. This document records the projects and public methodology reviewed, not claims that SIGNAL duplicates their systems or matches their accuracy. URLs were publicly retrievable during research; package tests did not access the live internet.

## Evaluated projects and transferable techniques

| Source | Method/idea reviewed | SIGNAL 0.2 adaptation |
|---|---|---|
| [Metaculus/forecasting-tools](https://github.com/Metaculus/forecasting-tools) | Forecast question contracts, reports, multiple individual predictions, benchmarking | Precise question/target/resolution, multiple local estimates, immutable resolution ledger |
| [forecastingresearch/forecastbench](https://github.com/forecastingresearch/forecastbench) | Dynamic, ex-ante evaluations avoid test-set answer leakage | As-of filter on publication **and first collection**; no claim of skill until future outcomes resolve |
| [FRI Metaculus Q2 forecasting bot](https://github.com/forecastingresearch/forecastbench_metaculus_forecasting_bot_q2) | Retrieval → research context → parallel forecasting → synthesis | Selected RSS evidence → deterministic topic expansion → three-lens local forecasts → median audit. **Sequential rather than parallel**, since a workstation may only load one model. |
| [hamza01055/hotpulse](https://github.com/hamza01055/hotpulse) | Event-focused source grouping, diversity and freshness | Clustering same-topic RSS headings, publisher-domain counts, dated evidence packet |
| [sefton37/sieve](https://github.com/sefton37/sieve) | SQLite ingestion, deduplication, related article context and local LLM analysis | Keep SQLite and identify related events; no embedding dependency |
| [Finn763/foresight](https://github.com/Finn763/foresight) | Base rates, aggregated forecasts and scored calibration | Outside-view role, user-supplied baseline provenance, median aggregation, per-method Brier |
| [Josh-Buck/RSSNews](https://github.com/Josh-Buck/RSSNews) | Local RSS ranking and source diversity tagging | Continue keyless local RSS, explicit source distinctions; no political-lean classifier added |
| [OpenForecaster/futuresim](https://github.com/OpenForecaster/futuresim) | Time-gated event forecasting | Strict as-of availability and immutable forecast audit |

Peer-reviewed foundation: Danny Halawi et al., [*Approaching Human-Level Forecasting with Language Models*, NeurIPS 2024](https://arxiv.org/abs/2402.18563). It combines retrieval, model reasoning and forecast aggregation. The present release follows the **conceptual pattern** but does **not** recreate the paper's retrieval corpus, training, expert forecasts or reported benchmarks.

Related calibration work: [AIA Forecaster: Technical Report (2025)](https://arxiv.org/abs/2511.07678), which highlights searching high-quality news, reconciliation and statistical calibration. SIGNAL has not implemented a learned calibration layer: data are insufficient at present.

Technical reference: [LM Studio OpenAI compatibility](https://lmstudio.ai/docs/developer/openai-compat) and [structured output guidance](https://github.com/lmstudio-ai/docs/blob/main/1_developer/3_openai-compat/structured-output.md). SIGNAL uses JSON-object requests with a validated-parser fallback for models/backends that do not support JSON mode.

## Concrete 0.2 forecasting pipeline

```text
1. USER SELECTS seed headline(s) from local RSS cache
2. RETRIEVE weighted lexical near-event matches collected on/before now/as-of
   - time limit; publisher diversity; avoid unrelated keyword-only matches
   - show exact evidence packet before inference
3. CREATE dated, externally resolvable YES/NO question (one local inference)
4. FORECAST same immutable question with 3 different reasoning lenses
   - outside view: reference class, baseline where verified
   - inside view: mechanisms, incentives, timelines
   - red team: contradictions, failure modes, disconfirmation
   - optional up to 3 local model IDs; default same model
5. VERIFY structured replies, probability bounds and ID citations
6. AGGREGATE the median of >=2 valid votes, preserving all disagreements
7. COMMIT question + probability + evidence + audit atomically in SQLite
8. INDEPENDENTLY RESOLVE outcome later, calculate Brier/reliability by method
```

## Explicit non-claims and safety limits

- **Headlines are insufficient to establish truth.** Different domains may copy the same wire report. Event clustering is a topic-match suggestion, not fact verification. The source packet shows original URLs and near-identical titles for review.
- **Only evidence that was *actually* available at the cutoff is eligible.** An article published before an old as-of date but first fetched afterwards is excluded. There is no reconstituted time travel.
- **No fake historical frequencies.** If a source-backed reference class is unknown, the prompt must say so. User-entered baseline numbers are tagged user-supplied, not validated.
- **Aggregation ≠ calibrated probability.** Repeated calls to the *same* model are correlated. No learned shrinkage, model weights or calibration transformation are applied before prospective evaluation. Tracking the spread is diagnostic, not a statistical confidence interval.
- **No automated adjudication.** Every yes/no answer must be entered against its original resolution contract with an external URL. No automatic claim that a model got something right.
- **No hidden internet access by models.** The user separately starts RSS collection; local inference only consumes cached excerpts.

## Measurement plan for later versions

1. Build a *prospective* set of pre-registered questions and outcome sources, including difficult and low-confidence cases. Track missing and ambiguous resolutions, not just wins.
2. Score quick single-model forecasts and multi-perspective forecasts **on the same questions and identical evidence cutoffs** to measure whether extra calls actually improve Brier/log-loss and calibration.
3. Validate against a simple prior / baseline where a defensible reference class exists, and show sample sizes and error bars. Do not infer improvement from 5–10 settled questions.
4. Research contrasting primary documents (official statistics, central bank releases, legislative schedules) and search for *contrary* rather than only similar headlines. Add a source-origin graph to distinguish syndication from firsthand reporting.
5. Add opt-in periodic reassessment with strictly timestamped probabilities, and prevent overwriting earlier forecasts. Score each forecasting horizon fairly without data leakage.
6. Consider an *optional* local embedding model for cross-language and paraphrase matching only after adding fixtures for false joins and false negatives. Do not make a vector DB or cloud service mandatory for Marble Oracle.
7. Evaluate runtime, RAM/VRAM and per-forecast model-call costs for LM Studio on Fedora/Windows. Reduce context when local model limits are reached, without fabricating summaries.

## Source-code policy

All code in `news_oracle/research.py`, `forecasting.py` and associated patches was independently authored for SIGNAL. External libraries/projects are cited as methodological references, not vendored or incorporated as code. Existing v0.1 local storage and standalone launcher remain backward compatible.

---

## 0.3 methods — risk investigations, primary sources, and source-aware timing (22 November 2026)

SIGNAL 0.3 adds an explicitly **adverse-scenario stress test** rather than a blanket negative sentiment or mechanically higher probabilities. The investigative pass asks for potential incentives behind public actions, trade and market spillovers, alternative ordinary explanations, disconfirming signals, and evidence IDs. An LLM can still hallucinate or make poor inferences: citation IDs are checked against the input, not factual veracity. Forecast evaluation is unchanged: compare outcome probabilities to subsequent resolutions rather than choose the most alarming narrative.

Cross-sector leads identify other *cached, time-eligible* stories that share distinctive terms while belonging to different focus areas. This is lexical retrieval, not an empirical correlation statistic or a graph proving relationships. The research packet and audit carry the proposed links and warnings so a human can inspect them before trusting an interpretation.

**Official publication RSS documentation:**
- WTO RSS feeds, https://www.wto.org/english/res_e/webcas_e/rss_e.htm (official feed URL listed there: `https://www.wto.org/library/rss/latest_news_e.xml`)
- ECB RSS index, https://www.ecb.europa.eu/home/html/rss.en.html (press release feed `https://www.ecb.europa.eu/rss/press.html`)
- US Federal Reserve RSS feeds, https://www.federalreserve.gov/feeds/feeds.htm (`https://www.federalreserve.gov/feeds/press_all.xml`)

**Official date reference examples for manual calendar entries / future structured adapters:**
- FRED Economic Release Calendar: https://fred.stlouisfed.org/releases/calendar
- IMF release calendar: https://data.imf.org/en/Release-Calendar
- BIS statistics release calendar: https://data.bis.org/release-calendar
- WTO meetings calendar subscription: https://www.wto.org/english/news_e/events_e/events_subscription_e.htm

These links are *sources to consult* and are not automatically ingested by this release. A website calendar is not evidence that a substantive forecast outcome will occur. Date-only resolution deadlines and model-proposed windows remain explicitly different event types. SIGNAL 0.3 exports all-day iCalendar records and retains the original source URL and uncertainty explanation.

## v0.4.0 research-to-code crosswalk (22 November 2026)

| Research pattern | Integrated implementation | Constraint |
|---|---|---|
| WorldReasoner/ForecastBench point-in-time evidence | `Store.forecast_packets` + SHA-256, historical `eligible` cutoffs | Timestamps reflect first collection, not complete original publisher history |
| NGEC event extraction | `event_graph.py` extracted reported claims with verbatim source quote and article ID | Quoted excerpt is not verified true; date needs explicit source text |
| Metaculus targeted disagreement/gap search | `gap_research.py` local model plan, bounded cached-term evidence retrieval | Does not fetch new articles or prove independence |
| ForecastBench outside-view baseline | `reference_classes` source-described user-supplied empirical frequency | Small/broad samples untrustworthy; no automatic empirical calibration |
| Subjective time-to-event forecasts | `timing.py` validated monotone conditional CDF; calendar interval masses | Estimated probabilities are subjective and uncalibrated |
| ForecastBench prospective evaluation | Brier by method, reliability bins, naive 50% score baseline | Not yet paired or statistically conclusive |
| Pessimistic geopolitical simulations | Existing downside and stabilising scenario analyses, evidence IDs, contrary alternative | Speculative hypotheses never mechanically change probability |

**Not yet integrated**: ACLED data/LightGBM models, full historical economic time series, prospective benchmark runner, automated external adjudication, iterative external search/SearXNG, model fine-tuning, or ensemble calibration. They need data/licensing, correct time-series validation, and local-resource checks before inclusion.

---

## v0.5 scope-selection and reporting implementation

`news_oracle.scopes.select_coverage()` uses cached RSS metadata (not exhaustive market coverage), excludes articles whose recorded first observation or publication time is in the future, skips items older than 14 days, removes exact duplicate headlines, and selects up to 16 recent sources with a source-domain diversity pass. It records matching/fresh/selected counts. These are selection counts, not measured source independence or epistemic confidence.

`NewsOracleEngine.overview()` produces a **qualitative multi-theme scope analysis** with evidence-ID validation on themes and watch signals; it saves the report as a normal briefing and explicitly separates downside and stabilising paths. It deliberately avoids making one fabricated numerical claim about all stocks or all global events. A deep scope forecast is instead still one objective yes/no forecast drawn from the scope sample, with frozen evidence, optional investigation and timing analysis. Neither system is calibrated on resolved real-world outcomes.

---

## v0.6.0 — What the strongest forecasting systems do, and what SIGNAL adopted (23 November 2026)

Research question: which techniques **measurably** improve AI forecasting, and how do professional forecasters make **broad** strategic predictions rigorous? Sources are public write-ups and papers. Their reported numbers come from frontier cloud models with web search. SIGNAL runs smaller local models on cached RSS, so **gains of the same size should not be expected**. Every adopted change must still earn its place on SIGNAL's own resolved forecasts.

### Evidence summary

| Finding | Source | Strength | SIGNAL v0.6 response |
|---|---|---|---|
| Averaging independent runs beats a single run. Brier (lower is better) was 0.1140 for the mean of 10 runs vs 0.1182 for a single run. Mean, median and trimmed mean were all within 0.0004 of each other. | [AIA Forecaster technical report (2025)](https://arxiv.org/abs/2511.07678), ensembling table | Ablation on one benchmark | **RUNS** setting (1–5, default 3). Runs after the first use shuffled evidence order and temperature 0.7. Aggregated in code: median for ≤3, trimmed mean for 4+. |
| Asking an LLM to aggregate forecasts did worse than a simple mean (it overweights outliers). | AIA report; [BLF, Murphy 2026](https://arxiv.org/abs/2604.18576) | Two independent reports | Aggregation stays numeric. The model never writes the final probability. |
| Winners aggregated multiple forecasts (86% of Fall 2025 winners). Cutting forecasts per question to save cost backfired. | [Metaculus synthesis of 11 analyses (May 2026)](https://forum.effectivealtruism.org/posts/Spyz3wESZu2eeqhDj/ai-forecasting-in-2026-what-11-analyses-say) | Survey correlation; the Spring 2026 survey did not replicate it (r = −0.19, n.s.) | Default 3 runs, kept modest for local hardware. Not presented as proven. |
| Multi-persona aggregation showed little or no improvement. | Metaculus synthesis | Small experiments | SIGNAL's three lenses are kept for transparency and audit continuity. Extra **independent runs** are added rather than more personas. |
| Research breadth and quality is the largest lever. Removing search worsened Brier about 3.6×, and the number of research sources correlated with score (r = 0.42). | Metaculus synthesis; AIA ablations | Consistent across seasons | Unchanged constraint: SIGNAL reads cached RSS only. Counter-evidence search remains. **Recommended:** more primary-source feeds (see below). |
| Checking similar past questions was associated with winning: 34% of winners vs 0% of non-winners (Fall 2025), and r = +0.34 (Spring 2026). | Metaculus synthesis; [Spring 2026 survey](https://forum.effectivealtruism.org/posts/tJoxFWkRev5wrEBar/what-ai-forecasting-strategy-works-best-spring-2026-survey) | Two seasons, correlational | `similar_history()`: SIGNAL's own lexically similar **resolved** questions and outcomes go to the outside view, labelled as reference outcomes, not evidence. |
| Decomposing questions into sub-questions improved Brier (0.132 vs 0.141). Researching sub-questions r = +0.24. | [Bosse et al., ICLR 2026 workshop](https://arxiv.org/abs/2601.22444); Spring 2026 survey | One controlled comparison plus a correlation | **BROAD OUTLOOK** is built on decomposition (below). |
| LLMs hedge toward 50%. Platt scaling on bot forecasts improved Brier by 0.016 (binary). Blind code extremising was *negatively* associated with score (r = −0.30, Spring 2026). | AIA report; Metaculus synthesis; Spring 2026 survey | Fitted calibration helps a little; unfitted extremising looks harmful | `calibration.py`: Platt scaling **fitted on the user's own resolved forecasts**, only with ≥40 resolved and both outcomes present. It is shown only if 10-fold cross-validated Brier beats the raw forecasts, as a separate display figure; the ledger is never altered. No blind extremising. |
| Reviewing the biggest misses helped (done by 66% of winners). Bots sometimes treat open questions as resolved. | Metaculus synthesis | Practitioner reports | Score report lists the 5 **biggest misses**. Prompts keep the "not already resolved" guard. |
| Pros' edge over bots came from *discrimination* (telling outcomes apart), not calibration. | Metaculus synthesis (Q4 2024) | One analysis | Interpretation note: calibration alone cannot close the gap; evidence quality matters. |
| Logically related LLM forecasts are often incoherent, and coherence correlates with accuracy. | [Paleka et al., ICLR 2025](https://arxiv.org/abs/2412.18544) | Peer-reviewed | Scenario sets are partitions: a run whose scenarios do not sum to 100% ± 10 is **rejected**, and small drift is normalised. Runs are pooled linearly so the result stays coherent. |

### Broad predictions: the question-cluster method

Professional forecasting faces a **rigour–relevance trade-off**. Broad strategic questions ("Where are global trade tensions heading?") matter most but cannot be scored, while scorable questions are narrow. The established answer is to forecast a *cluster* of specific questions that together bear on the broad one:

- **Good Judgment question clusters:** sets of discrete-event questions that, combined, shed light on a broader topic ([Good Judgment via Luckbox](https://luckboxmagazine.com/?p=14780); Tetlock's clustering proposal, [Edge Master Class](https://edge.org/node/26475)).
- **RAND Forecasting Initiative issue decomposition:** strategic issue → drivers → signals → forecast questions that are *specific, falsifiable, complementary and insightful*. The results are then "recomposed" into a dashboard, report or index ([RFI](https://randforecastinginitiative.org/rfi-blog/question-issue-decomposition)).
- **Metaculus Indexes:** a vague question answered on −100…+100 as a weighted average of component forecasts. Weights capture informativeness and direction ([announcement](https://forum.effectivealtruism.org/posts/W8CAJ6aw62cxKXmct/announcing-indexes-big-questions-quantified-2)).
- **FRI conditional trees** select questions by how much they would update the big question ([report](https://static1.squarespace.com/static/635693acf15a3e2a14a56a4a/t/66ba37a144f1d6095de467df/1723479995772/AIConditionalTrees.pdf)). SIGNAL uses the simpler weight-1–3 approach; value-of-information weighting is future work.

**SIGNAL BROAD OUTLOOK pipeline** (`news_oracle/outlook.py`, `NewsOracleEngine.broad_outlook`):

```text
cached scope sample (≤16 diverse RSS items, context-sized)
→ FRAMING call: strategic question, adverse direction, 2–4 drivers,
  3–4 mutually exclusive scenarios (status quo + adverse + stabilising),
  4–8 signposts {question, driver, resolution rule, date ≤ horizon, adverse_if YES/NO, weight 1–3, cited IDs}
  - invalid / vague / duplicate / out-of-horizon / uncited signposts are dropped and logged; ≥3 required
→ RUNS independent calls (run 1 original order at temp 0.2; later runs shuffled at temp 0.7):
  every signpost P(YES) 1–99 + scenario distribution (must sum to 100 ± 10) + citations
  - prompt asks for outside view first (how often comparable things happen over this horizon), then inside view
→ CODE aggregation: signpost = median / trimmed mean; scenarios = linear pool, renormalised;
  stress index = 100·Σ w·d·(2p−1)/Σw, d = +1 if YES is adverse; per-run index range recorded
→ ONE transaction: outlook + every signpost as a normal ledger forecast (frozen evidence, audit, SHA-256)
→ LATER: signposts resolve in the ledger (Brier/log loss); realised index = same formula with outcomes;
  scenario resolved after the horizon → multiclass Brier and log loss
```

Cost is **1 + RUNS** local model calls (4 at the default), fewer than a deep forecast (5–7) while producing 4–8 scored forecasts. The pessimistic lens shows up as an explicit adverse scenario and an adverse-direction index. It is never a multiplier on probabilities, and the run prompt says so.

### Considered and not adopted

- **Code extremising without data:** negatively associated with score in Spring 2026. Replaced by fitted, cross-validated recalibration.
- **LLM supervisor/reconciler (AIA):** the agentic version needs web search to resolve disagreements, which SIGNAL does not have. The non-agentic version is no better than a mean.
- **Learned model weighting (Two Heads, 2026):** needs ≥1,000 shared resolved sub-questions per model pair ([paper](https://arxiv.org/abs/2609.33257)). Revisit when the ledger is that large.
- **Prediction-market prices as input:** helpful in AIA's tests, but they need network access and accounts. Out of scope for local-first SIGNAL.

### Recommended next steps from this research

1. **Source breadth** is the highest-value gap: add official RSS feeds (IMF, OECD, BIS, national statistics offices, trade ministries), with provenance, after checking each feed is live.
2. Run 20–30 broad outlooks prospectively and resolve every signpost. Only then compare RUNS = 1 vs 3 and deep vs outlook signposts by Brier, on SIGNAL's own data.
3. Once ≥40 forecasts are resolved, check the recalibration slope `a`: a value above 1 means the local model hedges, as the literature predicts.


---

## OVERCAST 1.0 — Negative prognostication without losing accuracy (23 November 2026)

The goal is to **look hardest at what could go wrong** without letting that lens bias the numbers. Each device below follows a well-established risk-analysis or forecasting practice. SIGNAL/OVERCAST adapts it; none of them is claimed to raise accuracy by a measured amount here.

| Device | Established practice | Implementation | Guardrail |
|---|---|---|---|
| Pre-mortem | Klein's project pre-mortem: imagine failure has happened, then explain why. It surfaces risks that forward planning misses. | Required `premortem` narrative in the outlook framing; signposts are asked to come from its chain of events. | Labelled a stress test, not a prediction; it never sets a probability. |
| Scenario typing + tail risk | Scenario planning with explicit downside and low-probability/high-impact cases. | Scenario `kind` (adverse / tail_risk / status_quo / stabilising) and `severity` 1–5; "chance things go badly" = P(adverse + tail_risk). | At least one status-quo or stabilising scenario is required. The partition must sum to 100%. |
| Risk ranking | Risk matrices rank likelihood × impact. | Risk register: P(bad answer) × severity, newest revision only. | Ranking is separate from forecasting; probabilities are untouched. |
| Gloom bias | Calibration-in-the-large: mean forecast vs observed frequency. | Computed in the "bad-news" frame for oriented forecasts (signposts plus user-marked ones), with a 95% interval and a verdict at n ≥ 15. | Shows directly whether the pessimistic lens has leaked into the probabilities. |
| Frequent updating | Superforecasters update often, in small steps. | Outlook revisions on fresh news, with the same question and deadline; resolutions propagate across copies. | Originals are immutable. Every revision is scored, so stale forecasts are not hidden. |
| Early-warning sources | Breadth of research was the largest lever in the AI-forecasting evidence (v0.6 section). | Crisis Group, GDACS Orange/Red alerts, UN meeting coverage and Bank of England, each checked live on 23 Nov 2026. ReliefWeb, IMF and CNBC refused automated access; France 24 disallows robots. | Low-impact GDACS "Green" alerts are filtered out. Feed health is shown after each refresh. |

**Scoring caveat:** revisions create several ledger entries for one real-world question. Scores therefore weight frequently revised questions more, similar to time-averaged scoring. Filter by method or by the SIGNPOSTS view when comparing approaches.


---

## 1.1 — Review fixes that affect accuracy (23 November 2026)

- **Retrieval window.** Research breadth was the most consistent accuracy lever in the v0.6 evidence review. Retrieval had been silently capped at the newest 500 cached stories, which is roughly 1–3 days at 15 feeds. It now uses everything published or first seen in the last 15 days, up to 4,000 stories. The model still sees at most 16–22 selected items, because context is finite; what improved is the pool they are chosen from.
- **Independence of resolved questions.** Revisions resolve together. Treating them as separate outcomes would understate the uncertainty in the gloom-bias interval and let one question appear in both the training and test folds of the calibration check. Both statistics now keep one row per real-world question (the latest forecast), and the dashboard's track record reports the same per-question Brier score.
