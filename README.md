# OLED handheld deal watcher — Latent Vice Labs

Independent, conservative **10-minute** GitHub Actions deal watcher through **November 15, 2026**. Python standard library only. It never purchases anything.

## Setup

1. Create a **new non-fork** repository named `latentvicelabs/handheld-deal-watch` and put these files on `main`. **Do not install into the unrelated `workflow_templates` ComfyUI fork**: fork schedules are disabled by default and its workflows have other jobs.
2. In GitHub **Settings → Actions → General**, ensure Actions is enabled; in repository settings ensure Issues are enabled. Open **Actions → OLED handheld deal watch → Run workflow** for an initial execution and inspect the `report.json` artifact. Scheduled checks use `3,13,23,33,43,53` minutes of each hour (UTC); GitHub can delay/drop runs.
3. For mobile pushes (optional but recommended), create an unpredictable `ntfy.sh` topic and subscribe to it using the ntfy app. Set repository secret **`NTFY_TOPIC`** to the topic name; do **not** commit a topic secret. Otherwise exceptional deals create GitHub Issues (check GitHub notifications / Watch settings). GitHub Issues are not a guaranteed real-time push channel.
4. Review the Action logs/`report.json` after first run; merchants may block GitHub runner IPs. Failed sources are reported instead of producing fake prices. The existing hourly ChatGPT alert remains the independent fallback.

## Watched prices, USD **including US shipping, before tax**

| Exact product | Watch | Exceptional alert |
|---|---:|---:|
| Lenovo Legion Go 2 **Z2 Extreme**, 32GB | $1,100 | $1,000 |
| OneXFly F1 Pro **HX 370**, 32GB | $925 | $850 |
| ASUS ROG Xbox Ally **X20 2026 OLED**, 24GB | $1,100 | $1,000 |
| ZOTAC Zone OLED | $575 | $500 |
| Steam Deck **OLED 512GB** | $625 | $550 |

Direct sellers first. Only exact Shopify variants with explicit `available=true` and actual USD price can currently fire mobile/Issue alerts without additional checkout data. For the other direct merchant pages, the program checks explicit JSON-LD **InStock** and actual offer price, but **leaves shipping unverified** and *never automatically alerts* until shipping evidence is available. Discovery feeds (Slickdeals search RSS and Reddit RSS) are expressly for manual review and do not generate alerts. eBay is excluded: no noisy auction or unverified reseller alerts. No deal is claimed based on Google/Bing snippets, MSRP comparisons, a product's minimum variant price, or missing inventory evidence.

US shipping is set to $0 for ONEXPLAYER *devices*, per the manufacturer's US shipping policy; confirm ZIP-specific exceptions at checkout. ONEXPLAYER warranties and returns differ from Best Buy/Valve. Displayed 8% NY sales tax is an **estimate** and may not be collected by the merchant. Never interpret the estimate as a quote.

**Coverage limitation:** there is no reliable free universal product price/availability API. This is high-confidence partial coverage, not a comprehensive 10-minute scan of all retailers. Better feed/API integrations can be added without weakening the validation rules.

## Local

```bash
python -m unittest discover -s tests -v
python monitor.py # saves report.json; no GitHub issues unless in a GitHub Actions environment
```

Reports have direct scan failures and unverified RSS candidate links. Events generate one GitHub Issue per exact deal URL/condition; repeats are suppressed, and a price improvement of more than $25 adds a comment. No extra Actions secrets needed for GitHub Issues (`GITHUB_TOKEN` is automatic).
