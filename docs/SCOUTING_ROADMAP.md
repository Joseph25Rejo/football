# Club Scouting: improvement report and roadmap

Written 27 November 2026, after Phase 5 of the club-scouting build. This is a
scouting-first review **limited to the data the project already has**: StatsBomb Open
Data, Premier League 2015/16. No new data source, league or season is assumed.

Claims are marked **[verified]** when I checked them during this review, and
**[to confirm]** when they depend on something I could not inspect on this machine.

---

## 1. Summary

The product shows, for any of the 20 clubs, the squad, the strong and thin positions,
the weak team statistics and a ranked list of outside players who fit each gap. That
foundation is built.

Within this one dataset, the biggest improvements for a scout are:

1. **Trustworthy numbers.** Shrink small-sample rates, measure how stable ratings are
   across the season, and show uncertainty instead of a single score.
2. **Fairer ratings.** Reduce the style bias that makes low-possession sides rate low.
3. **Smarter squad and target logic.** Rotation, versatility, replacement search,
   system fit and risk flags, all from lineups and per-match data.
4. **A real scouting workflow.** Stages, structured scout reports, a player dossier
   and PDF export.
5. **A deeper metric layer from the raw events** (possession-value metrics,
   goalkeeper model, formations), which needs the raw data downloaded again.
6. **AI on top**: natural-language search, grounded report writing, and structuring
   scouts' notes, with a test harness built first.

Nothing here needs another data source. Section 3 lists what the data cannot answer,
so the product does not pretend to.

---

## 2. The data we have

### 2.1 What is on this machine now
Only the committed app database (`data/sample/app.duckdb`) is present **[verified]**:

| Table | Rows | What it holds |
|---|---|---|
| `mart_player_season` | 344 | One row per qualified player: per-90 metrics, role, within-role percentiles |
| `mart_player_match` | 10,450 | One row per player per match: counts for passes, shots, pressures, carries and so on |
| `fact_lineups` | 13,678 | Who was named, position, minutes, start and end minute |
| `dim_matches` | 380 | Every fixture with score, week, stadium, referee |
| `mart_team_match` | 760 | Team style features per match |
| `mart_team_season` | 20 | Team season means and spreads, with percentiles |
| `model_team_style` | 20 | Style cluster, label and nearest clubs |

The per-match tables are the key asset for this roadmap. They allow within-season
form, stability and uncertainty without any new data.

### 2.2 What needs the raw events re-downloaded
The raw layer (1.3 million events, about 1.2 GB) is gitignored and **not present on
this machine** **[verified]**. It can be rebuilt with `scripts/download_data.py` and
`scripts/build_staging.py`. Anything that reads individual events needs it: possession
value (VAEP, xThreat), pass-completion models, goalkeeper actions and formations.
StatsBomb's event format records each team's starting formation and tactical changes
**[to confirm in the raw files; the current pipeline does not keep them]**.

### 2.3 Coverage in numbers
- 380 matches, 20 clubs, one season.
- 344 players have enough minutes to be rated (600 or more).
- Goalkeepers are excluded by the pipeline.
- No ages, contracts, values, nationalities, injuries or video.

---

## 3. Out of reach with this data

Said plainly, so the product and its documents never imply otherwise:

- **Current squads.** Everything describes 2015/16.
- **Players outside the Premier League**, and any cross-league comparison.
- **Age, contract, market value, wages, nationality, injuries.** The source does not
  publish them.
- **Cross-season progression.** One season gives one observation per player.
- **Video and live scouting.** No footage is available.
- **Transfer-outcome backtests.** There is only one season, so there is nothing to
  test a recommendation against later.
- **Physical and tracking data.** Events only.

Why not go further: earlier research in this project found that FBref lost its Opta
advanced stats on 20 January 2026 after the provider terminated its licence **[verified:
Sports Reference blog]**. Staying on the open StatsBomb data avoids that kind of
licensing risk entirely.

---

## 4. Improvements, from a scouting point of view

### 4.1 Trustworthy numbers (uses `mart_player_match`, available now)
- **Sample-size shrinkage.** Pull rate statistics toward the role average when a player
  has few attempts, as the public ScoutLab app does for finishing and completion rates
  **[verified: its metric glossary]**. Stops a 25-shot striker looking elite.
- **Within-season stability.** Split each player's matches into two halves and
  correlate the two halves' ratings. Metrics that are not stable should carry less
  weight and a warning.
- **Uncertainty.** Resample a player's matches (bootstrap) to give a rating range, and
  show a "wide range" flag where minutes are low.
- **Form.** Rolling rating by match week, so a scout sees whether a player improved,
  declined or was steady.
- **Home and away splits**, and results against stronger and weaker opposition
  (opposition strength from the league table).

### 4.2 Fairer ratings (uses data we have)
- **Context adjustment.** Ratings reward volume, so a low-possession side's players
  rate low. Adjust passing and progression volume for team possession and territory,
  as defensive volume already is, and show before and after. This directly addresses
  the Leicester case documented in the model card.
- **Role fidelity.** Split the five role groups into more roles (holding midfielder,
  box-to-box, wing-back, inside forward), using the positions in `fact_lineups`.
- **Metric review.** Test each metric's usefulness with the stability work above and
  drop or down-weight the weak ones.

### 4.3 Squad intelligence (uses lineups and matches, available now)
- **Minutes concentration:** how dependent each role is on one player.
- **Rotation and role in the squad:** starter, regular substitute, fringe.
- **Versatility:** players used in more than one role, so thin positions can be
  covered internally before looking outside.
- **Availability gaps:** stretches of matches a regular missed. Reported as missed
  matches, never as injury, because the data cannot say why.
- **Consistency:** how much a player's output varies from match to match.

### 4.4 Target engine
- **Replacement mode:** "find someone like the player leaving", using the existing
  similarity engine with that player as the reference and the club's own squad
  excluded.
- **System fit:** compare a target's profile with what the club's style cluster
  needs, not only the gap.
- **Risk flags** beside the score, never inside it: low minutes, low coverage, wide
  uncertainty range, unstable metrics.
- **Comparables:** the nearest players to each target, so a scout can sanity-check.
- **Written rationale:** a short explanation of why a player is on the list (see
  section 5).

### 4.5 Scouting workflow (local, single user)
- **Pipeline stages:** Long list, Shortlist, Reviewed, Recommended, Rejected, with a
  reason for each rejection.
- **Structured scout reports:** grade, strengths, concerns, role and a recommendation,
  next to free-text notes.
- **Player dossier:** profile, comparables, risk flags, form chart, notes. Export to
  PDF.
- **Board one-pager:** the need, three shortlisted players, the case and the risks.
- **Audit trail:** who changed a status and when (single user, but still useful).

### 4.6 Deeper metrics from the raw events (needs the re-download)
- **Possession-value metrics** (VAEP and xThreat) through the open-source
  `socceraction` library, which reads StatsBomb data directly **[verified: project
  page]**.
- **Deep-zone involvement and receiving metrics**, which the ScoutLab glossary shows
  can be built from event coordinates.
- **Pass-difficulty model (xPass)** to judge completion rates against expectation.
- **Goalkeeper model** from goalkeeper events, filling the current gap.
- **Formation data and formation fit.** With real starting formations, the deferred
  formation analysis becomes grounded in what teams actually played rather than a
  guess **[to confirm in the raw files]**.

### 4.7 Validation (internal only)
- **Stability:** split-half and first-half-to-second-half correlations for every
  rating and metric.
- **Face validity:** known players should come out where football people expect, as
  already checked for similarity.
- **Panel review:** a scout or analyst rates the top ten targets for a few clubs.
- **What we cannot claim:** that a recommendation predicts success. State this on
  every page that shows a target.

---

## 5. AI and prompt engineering

AI needs no new data. It reads what the engine already produces.

### 5.1 Principles
1. **The engine owns the numbers.** Ratings, ranks and percentiles come from
   `src/scouting/`. The model receives them and writes about them. It never computes
   or invents a statistic.
2. **Ground everything.** Supply the facts in the prompt and require each claim to
   point to a supplied field. The Claude API supports citations over supplied
   documents and search-result blocks **[verified: Claude docs]**.
3. **Structured in, structured out.** Use structured outputs and strict tool use so
   results are valid and machine-checkable **[verified: Claude docs]**.
4. **Describe, do not predict.** The system prompt carries the product rule.
5. **A human decides.** The assistant drafts and explains.

### 5.2 Use cases that work on our data, in priority order

| # | Use case | How it works | Model tier |
|---|---|---|---|
| 1 | **Natural-language search** | "Strong progressive centre-back, 1,500+ minutes, not from Arsenal" becomes the existing `filter_players` criteria through a tool call; results come from the engine | Small, fast |
| 2 | **Report narrator** | Turns the report data (positions, weak stats, targets) into readable prose with no new numbers | Mid |
| 3 | **Scout-note structuring** | Converts a free-text note into grade, strengths, concerns and role, and flags what is missing | Small, fast |
| 4 | **Target rationale** | A two-sentence "why this player" from the drivers and risk flags | Small or mid |
| 5 | **Scouting assistant** | Chat with tools: search, profile, compare, squad diagnosis, shortlist. Confirms before any write | Mid |
| 6 | **Quality checker** | A second pass that checks a draft against the supplied data | Small, fast |
| 7 | **Notes synthesis** | Summarises several notes on one player and shows disagreements | Mid |

### 5.3 Models and cost
Current lineup and base prices **[verified: Claude docs, 27 Nov 2026]**:

| Model | API ID | Input / output per MTok | Use it for |
|---|---|---|---|
| Haiku 5.5 | `claude-haiku-5-5` | from $0.10 / $0.50 | Search parsing, note structuring, quality checks |
| Sonnet 5.5 | `claude-sonnet-5-5` | $2 / $10 | Report narration, synthesis, the assistant |
| Opus 5.5 | `claude-opus-5-5` | $4 / $20 | Harder multi-step questions |
| Fable 5.2 | `claude-fable-5-2` | $8 / $40 | Only if evaluations on Opus fall short |

All have a 1M-token context window. Batch requests are 50% cheaper, and prompt-cache
reads cost a small fraction of base input. A club report of about 3,000 input and
1,000 output tokens on Sonnet 5.5 costs roughly 1.6 US cents. Start with the cheapest
model that passes the evaluations.

### 5.4 Prompt engineering patterns
- **One versioned prompt per task** in a `prompts/` folder, reviewed like code.
- **Static first, data last.** Fixed rules, metric dictionary and report template at
  the start so prompt caching can reuse them **[verified: Claude docs]**; player data
  at the end.
- **Tagged inputs** (`<player_data>`, `<club_context>`, `<scout_notes>`) so
  instructions never blur with data.
- **Few-shot examples** of a good report, a good rejection note and a good
  "not enough data" answer.
- **Grounding rule:** "Use only values in `<player_data>`. If a value is missing, say
  it is unavailable. Do not estimate."
- **Audience templates:** head of recruitment, technical director, coach.
- **Flag-driven uncertainty:** hedging wording comes from the data flags (low
  minutes, wide range), not from the model's own confidence.

### 5.5 Evaluation harness (built before the features)
- A **golden set** of 30 to 50 inputs and approved outputs.
- An **automated numeric check**: every number in generated text must appear in the
  supplied data, or the test fails.
- A **banned-claim check**: no predictions or unsupported superlatives.
- **LLM-as-judge** for tone and completeness, spot-checked by a person.
- A **regression run** on every prompt or model change, tracking cost and latency.

### 5.6 Risks and safeguards
- **Invented statistics:** blocked by the numeric check and by giving the model no way
  to calculate.
- **Prompt injection:** scout notes are untrusted text. Keep them in tagged blocks and
  never let them alter tool permissions; confirm before writes.
- **Bias:** models can echo stereotypes. Do not put names or nationality-like cues
  into narrative prompts unless needed, and review samples.
- **Privacy:** scout notes are confidential. Decide what may be sent to an external
  provider before enabling any AI feature.
- **Over-trust:** label AI text as a draft and show the source fields beside it.
- **Cost drift:** cap tokens, cache fixed prefixes, batch bulk jobs.

---

## 6. Roadmap (continuing from Phase 5)

Effort: S about 1 to 2 days, M about 1 week, L multiple weeks. Ordered by dependency.

### Quick wins (available now)
- Replacement search from the club page: pick a squad player, find similar outsiders. (S)
- Club radar against the league average. (S)
- PDF export of the club report. (S)
- Data-quality badges (minutes, coverage, range) on every table. (S)

### Phase 6: Trustworthy numbers (M)
- Shrinkage, split-half stability, bootstrap ranges, form by match week.
- **Gate:** every rating shows a range; unstable metrics are flagged or down-weighted.

### Phase 7: Fairer ratings (M)
- Context adjustment for possession and territory; more role groups.
- **Gate:** side-by-side before and after for Leicester, with the finding written up.

### Phase 8: Squad intelligence (M)
- Minutes concentration, rotation, versatility, availability gaps, consistency.
- **Gate:** the club page flags a depth or dependence problem v1 could not see.

### Phase 9: Target engine v2 (M)
- Replacement mode, system fit, risk flags, comparables.
- **Gate:** for a chosen departing player, a ranked replacement list with risk flags.

### Phase 10: Scouting workflow (M)
- Pipeline stages, structured scout reports, dossier, PDF, audit trail.
- **Gate:** a target goes from long list to recommended, with a scout report and a
  one-page dossier.

### Phase 11: AI layer v1 (M)
- Evaluation harness first, then natural-language search, report narrator, note
  structuring, target rationale.
- **Gate:** passes the golden set with zero numeric errors.

### Phase 12: Raw-event metrics and assistant (L)
- Re-download the raw data; add VAEP and xThreat, xPass, a goalkeeper model, and
  formations (with formation fit if you want it).
- Tool-using assistant with confirmation on writes.
- **Gate:** new metrics validated against the old ones and documented in the metric
  dictionary.

### Phase 13: Validation and documentation (S)
- Stability report, panel review, updated model card and methodology.
- **Gate:** written findings and a clear statement of what the product does not claim.

---

## 7. Open questions
1. **Raw data:** are you happy to re-download the 1.2 GB raw layer for Phase 12?
2. **AI and notes:** may scout notes be sent to an external AI provider, or must AI
   features run only on engine output?
3. **Formations:** do you want formation fit included in Phase 12?
4. **Order:** should AI (Phase 11) move earlier, since it needs only the data we have?

---

## 8. Sources

Verified during this review (27 November 2026):
- StatsBomb Open Data, the project's only data source:
  https://github.com/statsbomb/open-data
- socceraction (VAEP and xThreat, StatsBomb reader):
  https://github.com/ML-KULeuven/socceraction
- ScoutLab public app and metric glossary, used as a design reference only:
  https://scoutlab.streamlit.app/
- Sports Reference, "FBref & Stathead Data Update", 20 January 2026 (why external
  free sources are risky):
  https://www.sports-reference.com/blog/2026/01/fbref-stathead-data-update/
- Claude documentation: models overview
  (https://platform.claude.com/docs/en/models/overview), structured outputs
  (https://platform.claude.com/docs/en/build-with-claude/structured-outputs), strict
  tool use
  (https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use),
  prompt caching
  (https://platform.claude.com/docs/en/build-with-claude/prompt-caching), citations
  (https://platform.claude.com/docs/en/build-with-claude/citations)

Internal sources: `METHODOLOGY.md`, `docs/MODEL_CARD.md`, `DATA_SOURCES.md`,
`artifacts/feature_config.yml` and the tables listed in section 2.1.

Set aside for now (outside the data we have): other football data providers and
scraped sites, which the previous draft of this report assessed. They matter only if
the project later moves beyond this dataset.
