# TasteDesk

**Know the fit before the check is written.**

## The problem

When a brand signs a celebrity, it is betting that the celebrity's fans will also like the brand. If they do, the campaign works. If they don't, the money is gone, and by the time anyone finds out the contract is already signed.

Today that bet is mostly made on weak signals: follower counts, how famous the star is, a gut feeling, or who the agent happens to know. Follower count tells you how many people watch a star. It does not tell you whether those people care about your product. Two stars with the same following can have fans with completely different tastes.

The same blind spot hurts the other side of the deal:

- **Brands** do not know which star's audience actually over-indexes on their product.
- **Talent agencies** do not know which brands to pitch for a client, so they pitch the obvious ones.
- **Ad agencies** have no clear evidence to show a client before the money is spent.
- Everyone is stuck when a star becomes too expensive, is already signed by a rival, or runs into a scandal, because nobody has a ranked backup ready.

## The solution

TasteDesk replaces the guess with a number. It measures how well a celebrity's fans already match a brand, using Qloo's taste graph, which tracks what people love across brands, music, film, TV and places.

Type a celebrity and a brand, and TasteDesk returns:

- **A Cultural Fit Score from 0 to 100.** It shows how strongly the star's fans point at this brand compared with 50 other brands. For example, Aveeno scores 100 for Jennifer Aniston's fans.
- **How unusual that fit is.** It is compared with other celebrity audiences, so a brand that everyone likes does not win by default.
- **Who is driving it.** The score is split by age group and gender.
- **Where they are.** A city map shows where that audience lives.
- **Taste twins.** These are the stars whose fans share the same taste, each scored for your brand. They work as ranked backups when the first choice is too expensive, already signed, or no longer an option.

You can also work the other way around. Enter a brand and get a ranked list of celebrities to sign, or enter a celebrity and get a list of brands to pitch. Or skip the forms and describe the deal in plain English, such as "We are Hyundai. Which celebrity should we sign?" A Gemini agent plans the steps and calls Qloo for every number.

The result is a clear, scored answer to the question every endorsement deal starts with: do this star's fans already love this brand?

## Why Qloo is necessary

Every number in TasteDesk comes from Qloo. Gemini only plans the steps and writes the summary. Take Qloo out and the app breaks:

- **No Fit Score.** To say Aveeno fits Jennifer Aniston's fans, you have to measure how strongly their taste points at Aveeno compared with 50 other brands. Only Qloo holds that taste data. Without it there is no score, only an opinion.
- **No audience lift.** Lift shows whether a result is unusual or just a brand everyone likes. It needs the taste of 34 other celebrity audiences to compare against, and all of them come from Qloo.
- **No segments or city map.** The age and gender split and the heatmap come straight from Qloo's demographic and location signals. Without Qloo you cannot say who is driving the fit or where those fans live.
- **No taste twins.** Twins come from Qloo's lookalike graph, which finds stars whose fans share the same taste, and each twin is then scored for your brand. Without it you would only get a list of famous names in the same genre, and no way to rank them for a brand.
- **No agent answers.** All five of the agent's tools call Qloo. Gemini plans the steps and writes the summary, but without Qloo's numbers it would have nothing to base a recommendation on except guesses.

A plain LLM can guess that Aveeno fits Jennifer Aniston. It cannot measure her fans' taste against 50 brands and 34 celebrity audiences, split that by age and gender, and find her twins.

## What it does

TasteDesk has four entry points:

- **Brands:** "Who do we sign?" Enter a brand and get celebrity audiences ranked by how much their fans over-index on it.
- **Talent agencies:** "Which brands fit my client?" Enter a celebrity and get a pitch list of the brands their fans love most.
- **Ad agencies:** "Is this pair worth it?" Enter a celebrity and a brand and get a fit score, rank, audience lift, segment breakdown, city heatmap and evidence trail.
- **Ask TasteDesk:** describe the deal in plain English. A Gemini agent plans the steps and calls Qloo for every number.

**Taste Twins** sits inside the dossier. For any celebrity it finds the stars whose fans share the same taste (5 people and 5 artists), then scores each one against your brand. Use it when the star is out of budget, when you already signed one twin and want to avoid paying twice for the same taste, or when you need a backup.

## Why it is Qloo-powered

An LLM can guess that Aveeno fits Jennifer Aniston. It cannot measure how strongly her fans' taste points at Aveeno compared with 50 other brands and 34 celebrity audiences, split that by age and gender, map it by city, and find her taste twins. That comes from Qloo's taste graph. Every score in the app is a Qloo result. Without Qloo there is nothing to compute.

Qloo endpoints used:

- `/search` to resolve celebrities and brands
- `/v2/insights` with `signal.interests.entities` and `filter.results.entities` for the pair score
- `/v2/insights` with `filter.type` set to person or artist for taste twins
- `signal.demographics.age` and `signal.demographics.gender` for segments
- `urn:heatmap` with `filter.location.query` for the city map

## How the score works

- **Raw affinity (0 to 1):** Qloo's own score for how closely a celebrity's fans match a brand.
- **Fit Score (0 to 100):** the share of the 50 reference brands that this brand beats for that celebrity. 100 means it beats all of them.
- **Brand rank:** where the brand lands among those 50.
- **Audience lift (σ, "sigma"):** how unusual the result is compared with other celebrity audiences. 0σ is average, +1σ is clearly above average, +2σ is rare (about 1 audience in 50), +3σ is extreme (about 1 in 1,000). It corrects for brands that everyone likes, such as Nike.

## Evidence

### Validation tests (notebook pipeline, `tastedesk.ipynb`)

### Test A: do real signed deals score high?

**What it tests.** The Fit Score is only useful if it points at deals that actually happened. This test checks whether Qloo ranks a star's real brand partners above the brands they have no known deal with. If the score were meaningless, a real deal would land in the middle of the pack, at a 50% percentile.

**How it was run.**
- We collected publicly documented deals: founder deals (Ryan Reynolds and Aviation Gin) and paid endorsements (Jennifer Aniston and Aveeno).
- The pipeline resolved 135 celebrities and about 194 brands in Qloo, then scored every celebrity x brand pair. That is 25,785 scored pairs from about 1,650 API calls.
- For each deal, we looked at the star's own row of brands and checked where the real partner brand ranks. A percentile of 0.90 means the real brand beats 90% of the other brands.
- A second check removes the "everyone likes Nike" effect. Each brand is z-scored across all celebrities, so the test asks whether a real deal stands out for that star specifically, not just for being a popular brand.

**Results (53 deals usable).**
- **Average percentile 0.749.** The real deal brand outranks about 75% of the other brands, against 50% by chance.
- **27 of 53 deals landed in the top 10%** of their celebrity's row. By chance, about 5 would. That is about 5x chance.
- **AUC 0.775 after removing brand popularity.** AUC is the odds that a random real deal scores higher than a random non-deal pair. 0.5 is a coin flip and 1.0 is perfect.
- **Endorsements scored 0.902 (n=19), founder deals 0.663 (n=34).** Paid endorsements are the strongest match with the Fit Score.
- **Stable.** The same pair returned the same score on five repeat calls.
- **Top hits:** Ryan Reynolds x Aviation Gin ranked #1 for his audience. Kim Kardashian x SKIMS, Kylie Jenner x Kylie Cosmetics, Tom Brady x TB12, Metallica x Blackened Whiskey, Reese Witherspoon x Draper James and Dwayne Johnson x Teremana also scored high.

### Test B: do Taste Twins hold up?

**What it tests.** Taste Twins are meant to be usable backups. That only holds if a twin's fans really share the star's taste, and if the star's brand deal also fits the twin. This test checks both, using random stars as the baseline.

**How it was run.**
- For 75 celebrities with documented deals, we pulled Qloo's lookalikes: 5 people and 5 artists each. 73 celebrities were usable, giving 708 twin rows.
- Every twin and every star was scored against a panel of 99 brands.
- Random controls were lookalikes of other celebrities, so each comparison was twin against random star.

**Check 1: taste agreement.** For each celebrity, we measured how closely each twin's brand ranking matches the star's (Spearman rank correlation, where 1.0 is identical order and 0 is unrelated).
- Twins match the star at **0.73**, against **0.43** for random stars.
- The gap is **+0.31**, with a 95% range of +0.26 to +0.35.
- Twins beat the random stars for **67 of 73** celebrities.

**Check 2: does the deal transfer?** We took each star's real deal brand and checked where it ranks in the twins' own brand lists.
- The deal brand sits at the **0.66** percentile for twins, against **0.50** for random stars. For the star herself it is 0.74.
- The gap is **+0.16**, with a 95% range of +0.11 to +0.21. Twins beat the random stars on **44 of 56** deals.
- In **40 of 56** deals, at least one twin ranked the deal brand in its top 10%. Random controls managed 31 of 56.

### Live app tests

**Test 1: Jennifer Aniston x Aveeno, with Taste Twins**

![Test 1 screenshot](assets/test1-aniston-aveeno.png)
*Aveeno is #1 of 50 brands for Aniston's audience, with fit score 100, raw affinity 0.97 and +2.9σ audience lift. Her fans rate it above all 34 celebrity audiences compared. By segment: all fans 0.97, under 35 0.88, 36 to 55 0.90, 55 and over 0.95, women 0.96, men 0.85. Taste twins scored for Aveeno: Courteney Cox 84, Julia Roberts 80.*

**Test 2: the Gemini agent, plain-English brief**
Brief: "We are Hyundai. Shortlist the 3 best celebrities, underwrite each one, and give a backup taste twin for our #1 pick."

![Test 2 screenshot](assets/test2-agent-hyundai.png)
*The agent called Qloo tools live and returned: Cedric the Entertainer 80 (best segment: under 35), Snoop Dogg 73 (men, under 35), Dwayne Johnson 59 (men, under 35). Backup for Cedric: Anthony Anderson, fit 86. Every number matches the app's own pages.*

**Test 3: Cedric the Entertainer x Hyundai, and a deliberate mismatch**

![Test 3 screenshot, Hyundai](assets/test3-cedric-hyundai.png)
*Hyundai tops Cedric's pitch list. Dossier: fit score 80 (strong fit), raw affinity 0.90, +2.5σ audience lift, rank #11 of 50.*

![Test 3 screenshot, Patagonia](assets/test3-cedric-patagonia.png)
*Cedric x Patagonia: fit score 4 (weak fit), raw affinity 0.76, 0.0σ (exactly average), rank #48 of 50. The app says no when the fit is not there, so its yes means something.*

Why Hyundai is #1 on the pitch list but #11 on the dossier: the pitch list ranks by audience lift, which removes the boost popular brands get. The dossier rank uses raw affinity across the 50 reference brands.

## The Gemini agent

The agent uses **Gemini 3.1 Flash-Lite** through the Gemini REST API with function calling. Gemini plans and writes. Qloo supplies every number.

- Five tools wrap the app's own functions: `find_talent_for_brand`, `find_brands_for_talent`, `underwrite_pair`, `audience_segments` and `find_taste_twins`.
- The system prompt requires that every score come from a tool result and that missing data is reported as "not enough data".
- The loop runs up to 12 steps at temperature 0.2. The tool calls show live in the UI, then Gemini writes a short verdict, a table and one risk note.
- If the step limit is reached, the agent is asked to write the answer from the data it already gathered.

## Repo structure

```
.gitignore         keeps API keys and the local Qloo cache out of the repo
LICENSE            MIT license
README.md          this file
requirements.txt   streamlit, pandas, pydeck, requests
tastedesk.py       the Streamlit app (UI, Qloo client, scoring, Taste Twins, Gemini agent)
tastedesk.ipynb    validation pipeline that produced the Test A and Test B results using Qloo
assets/            screenshots used in this README
```

## The Streamlit app

On first load, the app builds a comparison matrix: 36 celebrity audiences x 50 reference brands (34 celebrity audiences resolved when we tested), scored through Qloo. This takes about 30 seconds and is cached on the server for later visits. After that, any celebrity or brand you type is scored live. A brand outside the 50 costs about 36 extra Qloo calls, and a new celebrity costs 2.

Try it: [[LIVE_APP_URL]](https://taste-desk.streamlit.app/)

1. `pip install -r requirements.txt`
2. Set `QLOO_API_KEY` and `GEMINI_API_KEY` as Streamlit secrets or environment variables.
3. `streamlit run tastedesk.py`

## Who it helps

Celebrity deals run into millions, and until now the first question in every one of them, do this star's fans actually love this brand, was answered by instinct. TasteDesk answers it with a number.

- **Brand teams** walk into the negotiation with a ranked shortlist, the segment driving each fit, and a backup already scored. No more paying for a famous name and hoping.
- **Talent agencies** stop pitching the obvious brands. Every client gets a pitch list built from what their fans love, with the evidence to back each call.
- **Ad agencies** hand clients a one-page dossier with the score, the audience split and the city map, before a single dollar is committed.
- **Everyone** gets a ranked plan B. When a star is too expensive, already signed by a rival, or caught in a scandal, the swap is already scored.

The same engine extends to celebrity venture launches and sponsorships, wherever money is about to meet an audience.

TasteDesk does not predict sales. It measures how well a star's fans already match your brand, which is the bet behind every endorsement. That measurement has been missing from the table, and now it is one search away.

## Limitations

- Qloo has no pricing data, so you bring the budget when comparing twins.
- Some brands are missing from Qloo. 33 of 192 tested brands were not found, mostly small celebrity brands, and the app shows "Not enough data" for them.
- Paid-spokesperson deals (Allstate, Capital One, Ford, DirecTV) scored lower than endorsements and founder deals in Test A.
- The validation uses publicly documented deals, which is a proxy for what a deal is worth.
- The live Fit Score ranks against 50 reference brands, while Test A ranked against about 194.
- Taste twins include actors, musicians and athletes, and a few picks are loose matches.
- The first load after a server restart takes about 30 seconds.
