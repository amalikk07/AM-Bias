"""Fetch live market quotes from FMP into quotes.json for everyone who opens the site.
Runs in GitHub Actions; the key comes from the FMP_API_KEY repository secret."""
import json, os, sys, urllib.request, urllib.parse, urllib.error, datetime

KEY = os.environ.get("FMP_API_KEY", "").strip()

def fail(msg):
    # ::error:: lines show up as annotations on the run, without exposing the key
    print("::error::" + msg.replace(KEY, "***") if KEY else "::error::" + msg)
    sys.exit(1)

if not KEY:
    fail("FMP_API_KEY secret is missing or empty. Add it under Settings > Secrets and variables > Actions.")
BASE = "https://financialmodelingprep.com/stable/"
QUOTES = {"ndq": "^IXIC", "vix": "^VIX", "eur": "EURUSD", "jpy": "USDJPY"}
KEEP = ["symbol", "price", "changePercentage", "change", "dayLow", "dayHigh", "previousClose", "timestamp"]

def get(path, **params):
    params["apikey"] = KEY
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"HTTP {e.code} {body}".replace(KEY, "***"))

try:
    old = json.load(open("quotes.json"))
except Exception:
    old = {}

out = {"q": {}, "yld": old.get("yld", []), "yldDay": old.get("yldDay", "")}
errors = []
for key, sym in QUOTES.items():
    try:
        data = get("quote", symbol=sym)
        if isinstance(data, list) and data:
            out["q"][key] = {k: data[0].get(k) for k in KEEP}
        else:
            errors.append(f"{sym}: {str(data)[:120]}")
    except Exception as e:
        errors.append(f"{sym}: {e}")
        if key in old.get("q", {}):
            out["q"][key] = old["q"][key]

today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
if out["yldDay"] != today:
    try:
        frm = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
        rates = get("treasury-rates", **{"from": frm, "to": today})
        if isinstance(rates, list) and rates:
            out["yld"] = [{"date": r["date"], "year10": r["year10"]} for r in rates[:5]]
            out["yldDay"] = today
    except Exception as e:
        errors.append(f"treasury-rates: {e}")

for e in errors:
    print("::warning::" + e.replace(KEY, "***"))
if not out["q"]:
    fail("No quotes fetched: " + " | ".join(errors))
# Only stamp a new time when prices actually moved, so off-hours runs don't create commits
if out["q"] == old.get("q") and out["yld"] == old.get("yld"):
    print("No change")
    sys.exit(0)
out["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
json.dump(out, open("quotes.json", "w"), indent=1)
print("Updated", out["updated"], "errors:", errors)
