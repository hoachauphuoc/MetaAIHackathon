Moved from the README; the README has the short version.

# Role Assistant Foundry: impact and costs

## Impact

The figures below are external, linked, not measured by us, and quoted as published. The right-hand column is a design response: what the product does about each finding, not a measured reduction in worry, leaks or time.

| Finding (external, linked, not measured by us) | Source | Design response (not measured impact) |
|---|---|---|
| 52% of US workers feel worried about future AI use in the workplace, 36% hopeful (n = 5,273 employed adults, published 25 Feb 2025) | [Pew Research Center](https://www.pewresearch.org/social-trends/2025/02/25/u-s-workers-are-more-worried-than-hopeful-about-future-ai-use-in-the-workplace) | Assistants help with documents; four skills that evaluate, rank, monitor or decide about people are never available (tested) |
| 81% of US adults say AI used to monitor how workers do their jobs would make workers feel inappropriately watched (fielded 12-18 Dec 2022, n = 11,004 adults) | [Pew Research Center](https://www.pewresearch.org/internet/2023/04/20/ai-in-hiring-and-evaluating-workers-what-americans-think) | No performance or habit metrics exist in the data model; approvals keep a hash of the invite name only, to stop one person approving twice |
| 48% of respondents entered non-public company information and 45% entered employee information into GenAI tools (Cisco's own 2024 Data Privacy Benchmark survey, n = 2,600 privacy and security professionals) | [Cisco](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m01/organizations-ban-use-of-generative-ai-over-data-privacy-security-cisco-study.html) | Chat is never stored on the server; Standard mode only; a Private mode path for open weights |
| 45% of US employees used AI at work at least a few times a year in Q3 2025, 10% daily (fielded 5-19 Aug 2025) | [Gallup](https://www.gallup.com/workplace/699689/ai-use-at-work-rises.aspx) | Role jobs make AI useful for the daily job without writing prompts (a design choice; no test enforces it) |
| 22.4% of owner time goes to administrative tasks plus legal and compliance (UENI's own survey, n = 837 US businesses with five or fewer employees, May 2024) | [UENI](https://ueni.com/en-us/small-business-research/how-microbusiness-owners-spend-their-time) | The morning brief lists open documents by role so the owner sees what waits on whom; the model writes words, code picks the documents |
| 11 hours a week on administrative or finance tasks (American Express SME Barometer, a company-run survey, n = 1,000 UK owners, July 2026) | [Retail Times](https://retailtimes.co.uk/amex-sme-barometer-small-business-owners-spend-nearly-twice-the-time-on-admin-than-growing-their-business/) | Handoffs carry a checked form instead of a chat thread. We measured accuracy, not hours saved |
| 66% of US adults agree AI-based worker evaluation would lead to the collected information being misused (Pew, 20 Apr 2023) | [Pew Research Center](https://www.pewresearch.org/internet/2023/04/20/americans-views-on-use-of-ai-to-monitor-and-evaluate-workers/) | Nothing is kept about how a person works, and the onboarding plan shows nobody, including the owner, how far a new hire got |
| 4.8 months average onboarding time for a new technical hire (Linux Foundation, 2024 State of Tech Talent, 418 records; tech roles, not small firms) | [Linux Foundation](https://www.linuxfoundation.org/blog/the-2024-state-of-tech-talent-report) | Day-One gives a new hire a first-three-days plan from their role's kit, and Kind exit lets a leaver hand over to their own team |
| 44% of informal microbusinesses keep systematic records, about three-quarters of those in notebooks (ILO survey, n = 1,400 firms in Guatemala, Honduras and El Salvador, working paper Oct 2025) | [Wharton School](https://accounting.wharton.upenn.edu/wp-content/uploads/2025/10/AguilarLindRamesh.pdf) | Paper to form turns a photo of the paper into a form a person checks. Measured on synthetic sheets only |

Four rows came from a research run (Claude Haiku, Sonnet and Opus helped as development tools; the product itself runs on Muse only); the other five are cited directly from the linked page. Three rows are a company's own survey (Cisco, UENI, American Express) and say so. The method and what the figures do not show are in [docs/research](research/README.md).

**Independent review.** On 2026-10-31 SOLIFAN (Japan) reviewed this repository once and reproduced abnormal cases locally. It found three high, one medium and one low issue; each is fixed, and H01, H02, H03 and M01 have regression tests (L01, the median formula, does not). The Japanese original, an English translation and the finding-to-fix table are in [docs/evidence/solifan](evidence/solifan/README.md). It is a limited technical review, not a quality certification, and it did not re-measure our figures.

## What it costs (measured per call; usage is an assumption)

The per-call prices are measured ([docs/MEASURED.md](MEASURED.md)). The usage counts are
**assumptions** for a 10-person company with 5 roles and 22 working days a month, in three
scenarios anchored on published figures where one exists: an illustration of how the measured prices add up, not a claim about any
company's bill.

- **Light:** 4 chat answers per person per day. ChatGPT's 18 billion messages a week from 700
  million weekly users is about 3.7 a day per user, most of it not about work ([NBER paper by OpenAI, 2025](https://cdn.openai.com/pdf/a253471f-8260-40c6-a2cc-aa93fe9f142e/economic-research-chatgpt-usage-paper.pdf)).
  5 orders a day through the team workflow.
- **Busy:** 24 chat answers per person per day, an assumption: 6 times the light figure, borrowing the ratio OpenAI reports between its heaviest enterprise workers and the median ([State of Enterprise AI, Dec 2025](https://cdn.openai.com/pdf/7ef17d82-96bf-4dd1-9df2-228f7f377a29/the-state-of-enterprise-ai_2025-report.pdf)), a different population from the light figure.
  20 orders a day.
- **All day:** 80 answers per person per day, one every 6 minutes over an 8-hour day (our assumption, no
  published figure). 50 orders a day: suppliers put a manual purchase order at 8 to 12 minutes
  ([Hobson & Company, via TradeCentric](https://tradecentric.com/blog/manual-order-processing-cost)), so
  50 is about 8 hours of handling for the team.

| | Light | Busy | All day |
|---|---|---|---|
| Setup, once (1 chart USD 0.038, one UI run; the 10-chart batch averaged USD 0.0134 (set 1); + 5 briefs USD 0.0047 each) | USD 0.06 | USD 0.06 | USD 0.06 |
| Chat answers, USD 0.0015 each | USD 1.32 | USD 7.92 | USD 26.40 |
| Workflow steps, 3 per order, under USD 0.01 each (upper bound used) | up to USD 3.30 | up to USD 13.20 | up to USD 33.00 |

Private mode (Glimmer on Modal) is billed per warm GPU hour, not per call, and is not in this table; its GPU cost is **not measured**. Photos (about
USD 0.002 per sheet, set 6) and morning briefs are left out; the cost of a fix suggestion is **not measured**. The
80-call cap and the daily cost ceiling protect the public demo; they are not a company's bill.
