#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
watch_lib.py - deterministic engine for the library currency-watch pipeline.

This is the NON-LLM half of the watch system. Everything here is deterministic
and auditable: feed discovery, URL canonicalization, main-text extraction,
content hashing, MinHash near-dup detection, the verbatim-quote faithfulness
gate, source-tier assignment, accept/reject routing, run-health metrics, and the
human review digest. The model (a per-library `claude -p`) only does the fuzzy
work (claim/quote extraction + the council panel); it is sandwiched between the
deterministic gates below and cannot fool the quote check or the router.

Design rules honored:
  * stdlib only (no third-party deps) - runs on a bare Windows Python.
  * UTF-8 file IO; anything PRINTED to the console is ASCII-only (cp1252 console).
  * never invent a date - dates are passed in or read from disk.
  * writes are atomic (temp file + os.replace) so a crash never half-writes state.
  * a non-fetched / shell / walled source is recorded, never fabricated.

Subcommands (see `python watch_lib.py -h`):
  migrate-meta   add last_checked + newest_content_date to every _meta.json
  discover       crawl a library's watched feeds -> new, tier-assigned candidates
  triage         extract + hash + MinHash dedup the fetched candidates
  verify-quotes  deterministic substring faithfulness gate on model proposals
  route          apply thresholds -> AUTO_INTEGRATE | QUEUE | REJECT
  digest         write the twice-weekly human review digest + run-health line
  canon-url      utility: print the canonical form of a URL
  fingerprint    utility: print the MinHash fingerprint of stdin text
  selftest       run built-in unit checks (NO network) - safety-gate proof
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------- #
# console / io helpers
# --------------------------------------------------------------------------- #

# Strip non-ASCII glyphs for the cp1252 console, but KEEP tab/newline/CR so
# multi-line output (e.g. JSON) is not flattened.
ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")


def aprint(msg):
    """Print ASCII-safe to stdout (cp1252 console cannot take unicode glyphs)."""
    sys.stdout.write(ASCII_RE.sub("?", str(msg)) + "\n")


def eprint(msg):
    sys.stderr.write(ASCII_RE.sub("?", str(msg)) + "\n")


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json_atomic(path, obj):
    """Write JSON UTF-8 via temp file + atomic replace (crash-safe)."""
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def read_jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def append_jsonl(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


# --------------------------------------------------------------------------- #
# URL canonicalization  (idempotency substrate - same article -> same key)
# --------------------------------------------------------------------------- #

# Tracking / session params that never change article identity.
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "mc_cid", "mc_eid",
    "ref", "ref_src", "ref_url", "referrer", "source", "cmpid", "spm",
    "igshid", "ncid", "yclid", "_hsenc", "_hsmi", "vero_id", "oly_anon_id",
}


def canonicalize_url(url):
    """Return a stable canonical form of a URL for dedup keys."""
    if not url:
        return ""
    url = url.strip()
    try:
        p = urllib.parse.urlsplit(url)
    except ValueError:
        return url
    scheme = (p.scheme or "https").lower()
    if scheme == "http":
        scheme = "https"  # treat http/https as the same article
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    # drop default ports
    netloc = host
    if p.port and not ((scheme == "https" and p.port == 443) or p.port == 80):
        netloc = "%s:%d" % (host, p.port)
    # filter + sort query params
    kept = []
    for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True):
        kl = k.lower()
        if kl in _TRACKING_KEYS:
            continue
        if any(kl.startswith(pre) for pre in _TRACKING_PREFIXES):
            continue
        kept.append((k, v))
    kept.sort()
    query = urllib.parse.urlencode(kept)
    path = p.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    # fragment dropped entirely
    return urllib.parse.urlunsplit((scheme, netloc, path, query, ""))


def domain_of(url):
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


# --------------------------------------------------------------------------- #
# HTML -> visible text  (mirrors vendor_source.ps1's strip logic)
# --------------------------------------------------------------------------- #

_SCRIPT_RE = re.compile(r"(?is)<script.*?</script>")
_STYLE_RE = re.compile(r"(?is)<style.*?</style>")
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_WS_RE = re.compile(r"\s+")

_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'",
    "&apos;": "'", "&nbsp;": " ", "&mdash;": "-", "&ndash;": "-",
    "&rsquo;": "'", "&lsquo;": "'", "&ldquo;": '"', "&rdquo;": '"',
    "&hellip;": "...",
}


def _unescape(text):
    for k, v in _HTML_ENTITIES.items():
        text = text.replace(k, v)
    # numeric entities
    text = re.sub(r"&#(\d+);", lambda m: _safe_chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: _safe_chr(int(m.group(1), 16)), text)
    return text


def _safe_chr(cp):
    try:
        return chr(cp)
    except (ValueError, OverflowError):
        return ""


def extract_visible_text(raw):
    """Strip scripts/styles/tags -> collapsed visible text. Accepts bytes or str."""
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
    text = _SCRIPT_RE.sub(" ", text)
    text = _STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = _unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def normalize_for_match(text):
    """Whitespace-collapsed, NBSP-normalized text for substring/quote matching."""
    if text is None:
        return ""
    text = text.replace(" ", " ").replace("​", "")
    # normalize the common smart-quote / dash variants so a curly-quote source
    # still matches a straight-quote claim (and vice versa).
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'),
                 ("”", '"'), ("—", "-"), ("–", "-"),
                 ("…", "...")):
        text = text.replace(a, b)
    return _WS_RE.sub(" ", text).strip()


def content_hash(text):
    """Stable SHA256 of normalized visible text (ads/tokens in tags are stripped).

    Defensive: strips HTML tags/attrs first, so the hash is identical whether the
    caller passes raw HTML or already-extracted text, and is unaffected by
    changing attributes/timestamps/ads that live inside tags.
    """
    norm = normalize_for_match(extract_visible_text(text)).lower()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# MinHash near-duplicate / idea-level dedup
# --------------------------------------------------------------------------- #

NUM_PERM = 64
SHINGLE_K = 5
# Conservative on purpose: a false "duplicate" silently drops a NOVEL item, so we
# only collapse genuinely-overlapping text. Verbatim-body reposts (the common echo)
# score ~0.8+; distinct ideas score <0.3. The panel is the deeper novelty check.
NEAR_DUP_JACCARD = 0.70


def _word_shingles(text, k=SHINGLE_K):
    words = re.findall(r"[a-z0-9]+", normalize_for_match(text).lower())
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def minhash(text, num_perm=NUM_PERM):
    """Deterministic MinHash signature (list of num_perm ints) of the text."""
    shingles = _word_shingles(text)
    if not shingles:
        return [0] * num_perm
    sig = []
    for seed in range(num_perm):
        seed_b = str(seed).encode("ascii")
        mn = None
        for sh in shingles:
            h = int(hashlib.blake2b(sh.encode("utf-8"), digest_size=8,
                                    person=seed_b).hexdigest(), 16)
            if mn is None or h < mn:
                mn = h
        sig.append(mn)
    return sig


def jaccard_est(sig_a, sig_b):
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    eq = sum(1 for x, y in zip(sig_a, sig_b) if x == y)
    return eq / float(len(sig_a))


def is_near_dup(sig_a, sig_b, threshold=NEAR_DUP_JACCARD):
    return jaccard_est(sig_a, sig_b) >= threshold


# --------------------------------------------------------------------------- #
# Gate C: verbatim-quote faithfulness  (deterministic - the loop closes here)
# --------------------------------------------------------------------------- #

def verify_quote_substring(quote, source_text):
    """
    True iff `quote` literally appears in `source_text` after whitespace/quote
    normalization. This is a string operation - a plausible hallucinated quote
    cannot pass it. Used to BLOCK any [verbatim] claim not present in the bytes.
    """
    q = normalize_for_match(quote)
    if not q:
        return False
    src = normalize_for_match(source_text)
    if q in src:
        return True
    # case-insensitive fallback (still exact-substring, just case-relaxed)
    return q.lower() in src.lower()


# --------------------------------------------------------------------------- #
# Gate A: source-tier assignment from the maintained allowlist
# --------------------------------------------------------------------------- #

DEFAULT_TIER = 3  # unknown domain -> lead-only, needs human promotion (poison defense)


def assign_tier(url, author, source_tiers):
    """
    Return integer tier 0/1/2/3 or 'X'. Match on domain first, then optionally
    narrow/raise by author. Unknown domain -> DEFAULT_TIER (3, lead-only).
    `source_tiers` shape: {"tiers": {"0": {"domains": [...], "authors": [...]}, ...},
                           "reject_domains": [...]}
    """
    dom = domain_of(url)
    reject = set(d.lower() for d in source_tiers.get("reject_domains", []))
    if dom in reject:
        return "X"
    tiers = source_tiers.get("tiers", {})
    # domains can be exact or suffix ("example.com" matches "blog.example.com")
    best = None
    for tname, spec in tiers.items():
        for d in spec.get("domains", []):
            d = d.lower()
            if dom == d or dom.endswith("." + d):
                t = _tier_to_int(tname)
                if best is None or t < best:  # lower number = more trusted
                    best = t
    # author-based promotion (e.g. a named expert on a shared platform)
    if author:
        al = author.strip().lower()
        for tname, spec in tiers.items():
            for a in spec.get("authors", []):
                if a.strip().lower() == al:
                    t = _tier_to_int(tname)
                    if best is None or t < best:
                        best = t
    return best if best is not None else DEFAULT_TIER


def _tier_to_int(name):
    name = str(name).strip().lower().replace("tier", "").strip()
    return int(name)


# --------------------------------------------------------------------------- #
# Gate / Router: deterministic accept/reject decision
# --------------------------------------------------------------------------- #

def route_candidate(c, auto_lane="off", calibration_green=False,
                    per_domain_cap=3, domain_accept_counts=None):
    """
    Decide AUTO_INTEGRATE | QUEUE | REJECT for one fully-processed candidate `c`.
    Deterministic: reads tier, fetch_status, quote pass, novelty, contradiction,
    and the panel verdict already attached. Auto-lane is the narrowest path and
    is gated on calibration being green AND auto_lane == 'tier0'.
    """
    domain_accept_counts = domain_accept_counts or {}
    trace = []

    tier = c.get("source", {}).get("tier", DEFAULT_TIER)
    fetch_status = c.get("source", {}).get("fetch_status")
    gate = c.get("gate", {})
    panel = c.get("panel", {})

    # ---- hard REJECT gates (deterministic, no panel needed) ----
    if tier == "X":
        return _decide(c, "REJECT", "tier X (reject-listed source)")
    if fetch_status != "vendored":
        return _decide(c, "REJECT", "source not vendored (pending/unreachable) - cannot cite")
    if gate.get("faithfulness_pass") is False:
        return _decide(c, "REJECT", "faithfulness fail - a [verbatim] quote is not in the bytes")
    if gate.get("novelty_pass") is False:
        return _decide(c, "REJECT", "duplicate / already captured (idea-level)")
    if gate.get("relevance_pass") is False:
        return _decide(c, "REJECT", "off-topic for this expert")

    # ---- contradiction always forces human review ----
    if gate.get("contradiction") is True:
        return _decide(c, "QUEUE", "contradicts an existing high-confidence/Tier-0 claim - human review")

    # ---- panel verdict (only present for survivors that reached the council) ----
    verdict = panel.get("verdict")
    if verdict == "NO_GO":
        return _decide(c, "REJECT", "panel NO_GO")

    # ---- AUTO_INTEGRATE: the narrowest lane, Phase 2 only ----
    can_auto = (
        auto_lane == "tier0"
        and calibration_green
        and tier == 0
        and gate.get("faithfulness_pass") is True
        and gate.get("novelty_pass") is True
        and verdict == "GO"
        and panel.get("borderline") is False
        and domain_accept_counts.get(domain_of(c.get("source", {}).get("url", "")), 0) < per_domain_cap
    )
    if can_auto:
        return _decide(c, "AUTO_INTEGRATE", "Tier-0, faithful, novel, panel GO with margin, calibration green")

    # ---- default: QUEUE for the human digest ----
    reasons = []
    if auto_lane != "tier0":
        reasons.append("auto-lane off")
    elif not calibration_green:
        reasons.append("calibration not green")
    elif tier != 0:
        reasons.append("tier %s (not Tier-0 auto-eligible)" % tier)
    elif panel.get("borderline") is True:
        reasons.append("panel pass was borderline (no margin)")
    return _decide(c, "QUEUE", "; ".join(reasons) or "queued for review")


def _decide(c, decision, trace):
    c = dict(c)
    c["decision"] = decision
    c["decision_trace"] = trace
    return c


# --------------------------------------------------------------------------- #
# Run-health metrics  (make a degrading run LOUD)
# --------------------------------------------------------------------------- #

def run_health(decisions, discovered=0, deduped=0, unreachable=0,
               gold=None, run_id="", library=""):
    n = len(decisions)
    accepted = [d for d in decisions if d.get("decision") in ("AUTO_INTEGRATE", "QUEUE")]
    rejected = [d for d in decisions if d.get("decision") == "REJECT"]
    eligible = [d for d in decisions if d.get("source", {}).get("tier") != "X"]
    vendored = [d for d in decisions if d.get("source", {}).get("fetch_status") == "vendored"]
    blocked_quotes = sum(
        1 for d in decisions
        for cl in d.get("claims", [])
        if cl.get("confidence_flag") == "verbatim" and cl.get("quote_present") is False
    )
    novel = [d for d in accepted if d.get("gate", {}).get("novelty_pass") is True]
    borderline = [d for d in decisions if d.get("panel", {}).get("borderline") is True]

    hp = {
        "run_id": run_id,
        "library": library,
        "discovered": discovered,
        "deduped_dropped": deduped,
        "unreachable": unreachable,
        "candidates_scored": n,
        "eligible": len(eligible),
        "accepted": len(accepted),
        "rejected": len(rejected),
        "accept_rate": round(len(accepted) / len(eligible), 3) if eligible else None,
        "source_verify_pass_rate": round(len(vendored) / n, 3) if n else None,
        "blocked_verbatim_quotes": blocked_quotes,
        "novelty_rate": round(len(novel) / len(accepted), 3) if accepted else None,
        "borderline_panel_count": len(borderline),
    }
    if gold is not None:
        hp["panel_vs_gold_agreement"] = gold.get("agreement")
        hp["gold_trap_catch_rate"] = gold.get("trap_catch_rate")
    return hp


# --------------------------------------------------------------------------- #
# Feed discovery  (network; validates before trusting bytes)
# --------------------------------------------------------------------------- #

MIN_FEED_BYTES = 200
INTERSTITIAL_MARKERS = (
    "just a moment", "checking your browser", "cf-browser-verification",
    "challenge-platform", "enable javascript", "please enable javascript",
    "please wait while we", "one moment", "ddos protection by",
    "attention required", "verifying you are human", "captcha",
)
DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _http_get(url, timeout=60, ua=DEFAULT_UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua,
                                               "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        ctype = resp.headers.get("Content-Type", "")
        data = resp.read()
    return data, ctype


def fetch_feed(url, timeout=60):
    """
    Fetch a feed/index. Returns (status, items, note):
      status in {"ok","unreachable"}; a wall/shell/empty -> "unreachable" (never
      silently empty). items = list of {"url","title","date","guid"}.
    """
    try:
        data, ctype = _http_get(url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - any network/HTTP error is unreachable
        return "unreachable", [], "fetch-error: " + ASCII_RE.sub("?", str(exc))[:160]

    if not data or len(data) < MIN_FEED_BYTES:
        return "unreachable", [], "empty/too-small response (%d bytes)" % len(data)

    low = data[:4000].decode("utf-8", errors="replace").lower()
    for m in INTERSTITIAL_MARKERS:
        if m in low:
            return "unreachable", [], "interstitial/bot-wall marker: '%s'" % m

    items = _parse_feed(data)
    if not items:
        # an HTML index with no parseable feed items -> caller may need a sitemap
        return "unreachable", [], "no parseable feed items (JS shell or HTML index?)"
    return "ok", items, "ok"


def _parse_feed(data):
    """Parse RSS / Atom / sitemap XML -> items. Returns [] if not parseable."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    items = []
    tag = root.tag.lower()

    def localname(t):
        return t.rsplit("}", 1)[-1].lower()

    # RSS: <rss><channel><item>
    for it in root.iter():
        ln = localname(it.tag)
        if ln == "item":  # RSS
            link = _findtext(it, ("link",))
            title = _findtext(it, ("title",))
            date = _findtext(it, ("pubdate", "date", "published", "updated"))
            guid = _findtext(it, ("guid", "id")) or link
            if link:
                items.append({"url": link.strip(), "title": (title or "").strip(),
                              "date": (date or "").strip(), "guid": (guid or link).strip()})
        elif ln == "entry":  # Atom
            link = _atom_link(it)
            title = _findtext(it, ("title",))
            date = _findtext(it, ("updated", "published"))
            guid = _findtext(it, ("id",)) or link
            if link:
                items.append({"url": link.strip(), "title": (title or "").strip(),
                              "date": (date or "").strip(), "guid": (guid or link).strip()})
        elif ln == "url" and "sitemap" in tag:  # sitemap <urlset><url><loc>
            loc = _findtext(it, ("loc",))
            date = _findtext(it, ("lastmod",))
            if loc:
                items.append({"url": loc.strip(), "title": "", "date": (date or "").strip(),
                              "guid": loc.strip()})
    return items


def _findtext(elem, names):
    for child in elem.iter():
        ln = child.tag.rsplit("}", 1)[-1].lower()
        if ln in names and (child.text or "").strip():
            return child.text
    return None


def _atom_link(entry):
    for child in entry.iter():
        ln = child.tag.rsplit("}", 1)[-1].lower()
        if ln == "link":
            href = child.get("href")
            rel = (child.get("rel") or "alternate").lower()
            if href and rel == "alternate":
                return href
            if href and not entry_has_alt(entry):
                return href
    return None


def entry_has_alt(entry):
    for child in entry.iter():
        ln = child.tag.rsplit("}", 1)[-1].lower()
        if ln == "link" and (child.get("rel") or "alternate").lower() == "alternate":
            return True
    return False


# --------------------------------------------------------------------------- #
# Subcommand: migrate-meta
# --------------------------------------------------------------------------- #

def cmd_migrate_meta(args):
    libroot = args.root
    today = args.today
    changed, skipped = [], []
    for name in sorted(os.listdir(libroot)):
        d = os.path.join(libroot, name)
        meta_path = os.path.join(d, "_meta.json")
        if not os.path.isdir(d) or not os.path.exists(meta_path):
            continue
        meta = read_json(meta_path)
        if not isinstance(meta, dict):
            skipped.append("%s (unparseable)" % name)
            continue
        base = meta.get("last_updated") or meta.get("last_checked") or today
        need = ("last_checked" not in meta) or ("newest_content_date" not in meta) \
            or ("watch" not in meta)
        if not need:
            skipped.append("%s (already migrated)" % name)
            continue
        meta.setdefault("last_checked", base)
        meta.setdefault("newest_content_date", base)
        meta.setdefault("watch", {
            "last_run_id": None,
            "last_checked": base,
            "newest_content_date": base,
            "queued_review_count": 0,
            "note": "watch state - see agents/tools/watch/. last_updated kept as alias of last_checked."
        })
        if args.apply:
            write_json_atomic(meta_path, meta)
        changed.append(name)
    aprint("migrate-meta: %d %s, %d skipped"
           % (len(changed), "applied" if args.apply else "would-change", len(skipped)))
    for c in changed:
        aprint("  + " + c)
    if args.verbose:
        for s in skipped:
            aprint("  . " + s)
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: verify-quotes
# --------------------------------------------------------------------------- #

def _verify_one(c):
    """Set claims[].quote_present + gate.faithfulness_pass for one candidate.
    Faithfulness FAILS CLOSED: a verbatim claim with no readable source text is
    treated as unverified (blocked)."""
    raw_path = c.get("source", {}).get("raw_src_path")
    source_text = ""
    if raw_path and os.path.exists(raw_path):
        source_text = extract_visible_text(read_bytes(raw_path))
    all_ok = True
    has_verbatim = False
    for cl in c.get("claims", []):
        if cl.get("confidence_flag") == "verbatim":
            has_verbatim = True
            present = verify_quote_substring(cl.get("quote", ""), source_text)
            cl["quote_present"] = present
            if not present:
                all_ok = False
        else:
            cl.setdefault("quote_present", None)
    if has_verbatim and not source_text:
        all_ok = False  # fail closed: cannot verify a verbatim claim against nothing
    c.setdefault("gate", {})["faithfulness_pass"] = all_ok
    return c


def cmd_verify_quotes(args):
    """Faithfulness gate (Gate C): for each candidate with source.raw_src_path +
    claims[{text,confidence_flag,quote}], mark claims[].quote_present and set
    gate.faithfulness_pass = (all verbatim quotes present)."""
    proposals = read_json(args.proposals, [])
    out = [_verify_one(c) for c in proposals]
    write_json_atomic(args.out, out)
    blocked = sum(1 for c in out if c.get("gate", {}).get("faithfulness_pass") is False)
    aprint("verify-quotes: %d candidates, %d blocked on faithfulness" % (len(out), blocked))
    return 0


def _seen_keys(libdir):
    """Load (canonical urls, content_hashes, fingerprints) already recorded for dedup."""
    urls, hashes, sigs = set(), set(), []
    for row in read_jsonl(os.path.join(libdir, "_seen.jsonl")):
        if row.get("url_canonical"):
            urls.add(row["url_canonical"])
        if row.get("content_hash"):
            hashes.add(row["content_hash"])
        if row.get("idea_fingerprint"):
            sigs.append(row["idea_fingerprint"])
    return urls, hashes, sigs


def _dedup_all(props, libdir):
    """Set gate.novelty_pass + dedup.{content_hash,idea_fingerprint} per candidate.
    A candidate is NOT novel if its canonical URL or content hash was already seen,
    its text near-dups an earlier seen fingerprint, or it near-dups an earlier
    candidate IN THIS batch (collapse echoes -> corroboration, not new ideas)."""
    seen_urls, seen_hashes, seen_sigs = _seen_keys(libdir)
    batch = []  # (content_hash, sig) of novel candidates seen so far this batch
    for c in props:
        src = c.get("source", {})
        text = ""
        rp = src.get("raw_src_path")
        if rp and os.path.exists(rp):
            text = extract_visible_text(read_bytes(rp))
        ch = content_hash(text) if text else None
        sig = minhash(text) if text else None
        c.setdefault("dedup", {})
        c["dedup"]["content_hash"] = ch
        c["dedup"]["idea_fingerprint"] = sig
        novel = True
        cu = canonicalize_url(src.get("url", ""))
        if cu and cu in seen_urls:
            novel = False
        elif ch and ch in seen_hashes:
            novel = False
        elif sig and any(is_near_dup(sig, s) for s in seen_sigs if isinstance(s, list)):
            novel = False
        elif sig and any(is_near_dup(sig, bsig) or ch == bch for bch, bsig in batch if bsig):
            novel = False
        c.setdefault("gate", {})["novelty_pass"] = novel
        if novel and (ch or sig):
            batch.append((ch, sig))
    return props


def _integrity_one(c, vendor_script, libdir, today, do_vendor=True, timeout=90):
    """Stamp source.fetch_status + sha256 via the vendor_source.ps1 integrity
    boundary (independent raw-bytes fetch). When do_vendor is False (offline test),
    keep the candidate's existing fetch_status and raw_src_path."""
    src = c.setdefault("source", {})
    if not do_vendor:
        src.setdefault("fetch_status", "vendored")
        return c
    url = src.get("url", "")
    if not url or not vendor_script or not os.path.exists(vendor_script):
        src["fetch_status"] = "pending"
        src["classification"] = "no-vendor-script"
        return c
    safe = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:80] or "src"
    out_dir = os.path.join(libdir, "raw_src", "watch")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, safe + ".vendor.html")
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", vendor_script,
             "-Url", url, "-OutFile", out_file, "-Fetched", today],
            capture_output=True, text=True, timeout=timeout)
        line = (proc.stdout or "").strip().splitlines()
        parsed = None
        for ln in reversed(line):
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    parsed = json.loads(ln)
                    break
                except ValueError:
                    continue
        if parsed:
            src["fetch_status"] = parsed.get("status", "pending")
            src["sha256"] = parsed.get("sha256")
            src["classification"] = parsed.get("classification")
            src["bytes"] = parsed.get("bytes")
            if parsed.get("status") == "vendored":
                src["raw_src_path"] = out_file  # verify the quote against the INDEPENDENT fetch
        else:
            src["fetch_status"] = "pending"
            src["classification"] = "vendor-no-json"
    except Exception as exc:  # noqa: BLE001
        src["fetch_status"] = "pending"
        src["classification"] = "vendor-error: " + ASCII_RE.sub("?", str(exc))[:120]
    return c


def _commit(libdir, decisions, run_id, today):
    seen_path = os.path.join(libdir, "_seen.jsonl")
    accepted_dates = []
    queued = 0
    for d in decisions:
        url = d.get("source", {}).get("url", "")
        append_jsonl(seen_path, {
            "url_canonical": canonicalize_url(url),
            "content_hash": d.get("dedup", {}).get("content_hash"),
            "idea_fingerprint": d.get("dedup", {}).get("idea_fingerprint"),
            "first_seen_run": run_id,
            "decision": d.get("decision"),
        })
        dec = d.get("decision")
        if dec in ("QUEUE", "AUTO_INTEGRATE"):
            if dec == "QUEUE":
                queued += 1
            dt = d.get("source", {}).get("fetched") or d.get("source", {}).get("date")
            if dt and re.match(r"^\d{4}-\d{2}-\d{2}", str(dt)):
                accepted_dates.append(str(dt)[:10])
    meta_path = os.path.join(libdir, "_meta.json")
    meta = read_json(meta_path, {})
    if isinstance(meta, dict):
        meta["last_checked"] = today
        if "last_updated" in meta:
            meta["last_updated"] = today
        newest = max([meta.get("newest_content_date") or today] + accepted_dates)
        meta["newest_content_date"] = newest
        w = meta.setdefault("watch", {})
        w["last_run_id"] = run_id
        w["last_checked"] = today
        w["newest_content_date"] = newest
        w["queued_review_count"] = w.get("queued_review_count", 0) + queued
        write_json_atomic(meta_path, meta)
    return len(decisions), queued


def cmd_commit(args):
    decisions = read_json(args.decisions, [])
    n, queued = _commit(args.library_dir, decisions, args.run_id, args.today)
    aprint("commit: %s  seen+=%d  queued+=%d  last_checked=%s"
           % (os.path.basename(os.path.normpath(args.library_dir)), n, queued, args.today))
    return 0


def cmd_postpass(args):
    """Full DETERMINISTIC post-pass for one library after the model produced
    proposals.json: tier-assign -> integrity (vendor_source.ps1) -> faithfulness
    -> dedup -> carry panel verdict -> route -> append digest + run-health -> commit
    (_seen + _meta). The model never decides what is written; this does."""
    libdir = args.library_dir
    props = read_json(args.proposals, [])
    if not isinstance(props, list):
        props = []
    st = read_json(args.source_tiers, {})
    libname = os.path.basename(os.path.normpath(libdir))

    for c in props:
        src = c.setdefault("source", {})
        src["tier"] = assign_tier(src.get("url", ""), src.get("author", ""), st)  # authoritative
        _integrity_one(c, args.vendor_script, libdir, args.today, do_vendor=not args.no_vendor)
    for c in props:
        _verify_one(c)
    _dedup_all(props, libdir)
    for c in props:
        g = c.setdefault("gate", {})
        g.setdefault("relevance_pass", True)
        g.setdefault("contradiction", False)
        cv = c.get("curation_verdict") or {}
        if cv:
            p = c.setdefault("panel", {})
            p.setdefault("verdict", cv.get("verdict"))
            p.setdefault("borderline", cv.get("borderline"))
            p.setdefault("margin", cv.get("margin"))
            p.setdefault("scores", cv.get("scores"))
            p.setdefault("strongest_dissent", cv.get("strongest_dissent"))

    decisions = []
    domain_counts = {}
    for c in props:
        d = route_candidate(c, auto_lane=args.auto_lane, calibration_green=args.calibration_green,
                            per_domain_cap=args.per_domain_cap, domain_accept_counts=domain_counts)
        if d.get("decision") == "AUTO_INTEGRATE":
            dom = domain_of(d.get("source", {}).get("url", ""))
            domain_counts[dom] = domain_counts.get(dom, 0) + 1
        decisions.append(d)

    # append this library's section to the shared run digest
    text = build_digest_text(decisions, args.run_id, library=libname, include_rejects=args.include_rejects)
    dd = os.path.dirname(os.path.abspath(args.digest))
    if dd and not os.path.isdir(dd):
        os.makedirs(dd, exist_ok=True)
    with open(args.digest, "a", encoding="utf-8") as fh:
        fh.write(text + "\n")

    gold = None
    if getattr(args, "gold", None) and os.path.exists(args.gold):
        gold = read_json(args.gold, None)
    append_jsonl(args.runhealth, run_health(decisions, discovered=len(props),
                                            gold=gold, library=libname, run_id=args.run_id))
    _commit(libdir, decisions, args.run_id, args.today)
    if args.decisions_out:
        write_json_atomic(args.decisions_out, decisions)

    counts = {}
    for d in decisions:
        counts[d["decision"]] = counts.get(d["decision"], 0) + 1
    aprint("postpass %s: %s" % (libname, ", ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())) or "(no candidates)"))
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: route
# --------------------------------------------------------------------------- #

def cmd_route(args):
    proposals = read_json(args.proposals, [])
    decisions = []
    domain_counts = {}
    for c in proposals:
        d = route_candidate(c, auto_lane=args.auto_lane,
                            calibration_green=args.calibration_green,
                            per_domain_cap=args.per_domain_cap,
                            domain_accept_counts=domain_counts)
        if d.get("decision") == "AUTO_INTEGRATE":
            dom = domain_of(d.get("source", {}).get("url", ""))
            domain_counts[dom] = domain_counts.get(dom, 0) + 1
        decisions.append(d)
    write_json_atomic(args.out, decisions)
    counts = {}
    for d in decisions:
        counts[d["decision"]] = counts.get(d["decision"], 0) + 1
    aprint("route: " + ", ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())))
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: digest
# --------------------------------------------------------------------------- #

def build_digest_text(decisions, run_id, library="", include_rejects=False):
    lines = []
    lines.append("# Library watch - review digest (%s)" % run_id)
    lines.append("")
    lines.append("Run: %s   Library scope: %s" % (run_id, library or "(multi)"))
    lines.append("")
    queued = [d for d in decisions if d.get("decision") == "QUEUE"]
    auto = [d for d in decisions if d.get("decision") == "AUTO_INTEGRATE"]
    rej = [d for d in decisions if d.get("decision") == "REJECT"]
    lines.append("Summary: %d queued for review, %d auto-integrated (Tier-0 lane), %d rejected."
                 % (len(queued), len(auto), len(rej)))
    lines.append("")
    if queued:
        lines.append("## QUEUED - needs your yes/no")
        for d in queued:
            lines.extend(_digest_block(d))
    if auto:
        lines.append("")
        lines.append("## AUTO-INTEGRATED (Tier-0, unreviewed - skim to confirm)")
        for d in auto:
            lines.extend(_digest_block(d))
    if rej and include_rejects:
        lines.append("")
        lines.append("## REJECTED (log)")
        for d in rej:
            lines.append("- [%s] %s - %s"
                         % (d.get("source", {}).get("tier"),
                            d.get("source", {}).get("url"),
                            d.get("decision_trace")))
    return "\n".join(lines) + "\n"


def _write_text(path, text):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def cmd_digest(args):
    decisions = read_json(args.decisions, [])
    text = build_digest_text(decisions, args.run_id, args.library, args.include_rejects)
    _write_text(args.out, text)
    q = sum(1 for d in decisions if d.get("decision") == "QUEUE")
    a = sum(1 for d in decisions if d.get("decision") == "AUTO_INTEGRATE")
    r = sum(1 for d in decisions if d.get("decision") == "REJECT")
    aprint("digest: wrote %s (%d queued, %d auto, %d rejected)" % (args.out, q, a, r))
    return 0


def _digest_block(d):
    src = d.get("source", {})
    panel = d.get("panel", {})
    out = []
    out.append("")
    out.append("### %s  (Tier %s)" % (d.get("target_expert", "?"), src.get("tier")))
    out.append("- Source: %s" % src.get("url"))
    out.append("- Decision: **%s** - %s" % (d.get("decision"), d.get("decision_trace")))
    if panel:
        out.append("- Panel: %s (margin %s%s); scores %s"
                   % (panel.get("verdict"), panel.get("margin"),
                      ", borderline" if panel.get("borderline") else "",
                      panel.get("scores")))
        if panel.get("strongest_dissent"):
            out.append("  - Dissent: %s" % panel.get("strongest_dissent"))
    for cl in d.get("claims", []):
        flag = cl.get("confidence_flag")
        present = cl.get("quote_present")
        mark = "" if present is not False else "  [BLOCKED: quote not in source]"
        out.append("  - [%s] %s%s" % (flag, cl.get("text", "")[:280], mark))
    return out


# --------------------------------------------------------------------------- #
# Utility subcommands
# --------------------------------------------------------------------------- #

def cmd_resolve_sources(args):
    """Expand a library's watch.json source_ids against watchlist.global.json +
    its extra_sources into one concrete list (deterministic, no network). Used by
    the runner's -DryRun and to build the per-library model prompt."""
    wl = read_json(args.watchlist, {})
    by_id = {s.get("id"): s for s in wl.get("sources", [])}
    watch = read_json(os.path.join(args.library_dir, "watch.json"), {})
    meta = read_json(os.path.join(args.library_dir, "_meta.json"), {})
    sources = []
    for sid in watch.get("source_ids", []):
        s = by_id.get(sid)
        if s:
            sources.append({"id": sid, "name": s.get("name"), "feed_url": s.get("feed_url"),
                            "kind": s.get("kind"), "tier": s.get("tier"),
                            "cadence": s.get("cadence"), "candidate_feeds": s.get("candidate_feeds", []),
                            "verified": s.get("verified", False), "fetch_notes": s.get("fetch_notes", "")})
        else:
            sources.append({"id": sid, "error": "unknown source id (not in watchlist.global.json)"})
    for ex in watch.get("extra_sources", []):
        sources.append({"id": "(extra)", "feed_url": ex.get("url"), "kind": ex.get("kind"),
                        "tier": ex.get("tier"), "verified": ex.get("verified", False),
                        "note": ex.get("note", "")})
    result = {
        "library": watch.get("library"),
        "class": watch.get("class"),
        "cadence": watch.get("cadence"),
        "expert_agent": watch.get("expert_agent"),
        "auto_lane": watch.get("auto_lane", "off"),
        "newest_content_date": meta.get("newest_content_date"),
        "last_checked": meta.get("last_checked"),
        "topics": watch.get("topics", []),
        "sources": sources,
    }
    if args.out:
        write_json_atomic(args.out, result)
        aprint("resolve-sources: %s -> %d sources -> %s"
               % (watch.get("library"), len(sources), args.out))
    else:
        aprint(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def looks_like_shell(text):
    """True if text is a bot-wall / JS shell / empty - not a real source body."""
    low = (text or "").lower()
    if any(m in low for m in INTERSTITIAL_MARKERS):
        return True
    return len(extract_visible_text(text)) < 40


def _gold_gate(item, source_tiers, prior_by_expert):
    """Run the DETERMINISTIC gates on one gold item -> (outcome, why).

    Outcomes: REJECT (tier X) | LEAD_ONLY (tier 3) | BLOCKED (shell or quote
    missing) | DUP (echo of an earlier passing item for the same expert) |
    PASS_TO_PANEL. Mirrors the order the real pipeline uses so a hallucination is
    BLOCKED before any dedup runs.
    """
    url = item.get("source_url", "")
    author = item.get("author", "")
    quote = item.get("verbatim_quote", "")
    text = item.get("source_text", "")
    tier = assign_tier(url, author, source_tiers)
    if tier == "X":
        return "REJECT", "tier X (reject-listed)"
    if tier == 3:
        return "LEAD_ONLY", "tier 3 social - lead only, never a citation"
    if looks_like_shell(text):
        return "BLOCKED", "source is a shell / bot-wall - cannot verify a quote"
    if quote and not verify_quote_substring(quote, text):
        return "BLOCKED", "verbatim quote not present in source bytes (hallucination)"
    expert = item.get("target_expert", "")
    ch = content_hash(text)
    sig = minhash(text)
    for prev_ch, prev_sig in prior_by_expert.get(expert, []):
        if ch == prev_ch or is_near_dup(sig, prev_sig):
            return "DUP", "near-duplicate of an earlier candidate for this expert"
    return "PASS_TO_PANEL", "passes deterministic gates (panel decides worth)"


def cmd_goldcheck(args):
    """Replay the gold set through the deterministic gates (NO network) and
    report trap-catch-rate + which traps only the panel can catch. Verification
    step 2: gates must BLOCK 100% of planted hallucination/pending and DUP the
    planted echo. Exit 1 on any mismatch vs each item's expected_gate."""
    st = read_json(args.source_tiers, {})
    items = read_jsonl(args.goldset)
    if not items:
        aprint("goldcheck: goldset is empty (%s)" % args.goldset)
        return 0
    det_traps = {"hallucination", "pending_cite", "echo", "lead_only"}
    panel_only = {"off_topic", "poison"}
    prior = {}
    mismatches = []
    trap_total = trap_caught = 0
    aprint("goldcheck (%d items) - deterministic gate replay" % len(items))
    for it in items:
        outcome, why = _gold_gate(it, st, prior)
        exp = it.get("expected_gate")
        ok = (outcome == exp)
        tt = it.get("trap_type", "none")
        flag = "ok  " if ok else "MISMATCH"
        aprint("  %s %-9s %-14s expect %-14s got %-14s" % (flag, it.get("candidate_id"), tt, exp, outcome))
        if not ok:
            mismatches.append((it.get("candidate_id"), tt, exp, outcome))
        if tt in det_traps:
            trap_total += 1
            if ok:
                trap_caught += 1
        if outcome == "PASS_TO_PANEL":
            prior.setdefault(it.get("target_expert", ""), []).append(
                (content_hash(it.get("source_text", "")), minhash(it.get("source_text", ""))))
    rate = (trap_caught / trap_total) if trap_total else None
    panel_items = [it.get("candidate_id") for it in items if it.get("trap_type") in panel_only]
    aprint("")
    aprint("deterministic trap-catch rate: %s (%d/%d)"
           % ("%.0f%%" % (rate * 100) if rate is not None else "n/a", trap_caught, trap_total))
    aprint("panel-only items (gate correctly passes; panel/human must judge): %s"
           % (", ".join(panel_items) or "(none)"))
    if args.out:
        write_json_atomic(args.out, {
            "trap_catch_rate": rate,
            "mismatches": mismatches,
            "panel_only_items": panel_items,
        })
    if mismatches:
        aprint("")
        aprint("GOLDCHECK FAILED: %d mismatch(es)" % len(mismatches))
        return 1
    aprint("GOLDCHECK PASSED")
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: goldpanel  (ADVISORY panel-vs-gold agreement; never gates)
# --------------------------------------------------------------------------- #

# council verdict -> gold human_label (canonical map)
COUNCIL_VERDICT_TO_LABEL = {
    "GO": "INCLUDE",
    "GO_WITH_CONDITIONS": "REVISE",
    "NO_GO": "REJECT",
}


def cmd_goldpanel(args):
    """ADVISORY (never gates): measure how the council's curation verdicts agree
    with the gold human labels on the PANEL-ONLY items (expected_gate ==
    PASS_TO_PANEL). The deterministic gates pass those items; only the panel +
    human gold-labeling can judge them, so this is the panel-vs-gold-agreement
    number that feeds run-health. Always returns 0 except when the input is
    genuinely unreadable/empty (and even then prints a clear message)."""
    items = read_jsonl(args.goldset)
    if not items:
        aprint("goldpanel: goldset is empty or unreadable (%s)" % args.goldset)
        return 1
    verdicts = read_json(args.verdicts, None)
    if not isinstance(verdicts, dict):
        aprint("goldpanel: verdicts file is empty or not a JSON object (%s)" % args.verdicts)
        return 1

    panel_items = [it for it in items if it.get("expected_gate") == "PASS_TO_PANEL"]
    rows = []
    evaluated = matches = missing = 0
    for it in panel_items:
        cid = it.get("candidate_id")
        hl = it.get("human_label")
        raw = verdicts.get(cid)
        if isinstance(raw, dict):
            verdict = raw.get("verdict")
        else:
            verdict = raw
        if verdict is None:
            missing += 1
            rows.append({"candidate_id": cid, "human_label": hl,
                         "council_verdict": None, "mapped": None,
                         "match": False, "status": "MISSING"})
            continue
        evaluated += 1
        mapped = COUNCIL_VERDICT_TO_LABEL.get(verdict)
        match = (mapped == hl)
        if match:
            matches += 1
        rows.append({"candidate_id": cid, "human_label": hl,
                     "council_verdict": verdict, "mapped": mapped,
                     "match": match, "status": "OK" if match else "MISMATCH"})
    agreement = round(matches / evaluated, 3) if evaluated else None

    aprint("goldpanel (%d panel item(s)) - council verdict vs gold label" % len(panel_items))
    aprint("  %-9s %-12s %-18s %-8s %s" % ("cand_id", "human_label", "council_verdict", "mapped", "result"))
    for r in rows:
        aprint("  %-9s %-12s %-18s %-8s %s" % (
            r["candidate_id"], r["human_label"],
            r["council_verdict"] if r["council_verdict"] is not None else "(none)",
            r["mapped"] if r["mapped"] is not None else "(none)",
            r["status"]))
    aprint("")
    aprint("panel-vs-gold agreement: %s (%d/%d matched); missing: %d"
           % ("%.1f%%" % (agreement * 100) if agreement is not None else "n/a",
              matches, evaluated, missing))

    if args.out:
        out = {
            "agreement": agreement,
            "evaluated": evaluated,
            "matches": matches,
            "missing": missing,
            "detail": [
                {"candidate_id": r["candidate_id"], "human_label": r["human_label"],
                 "council_verdict": r["council_verdict"], "mapped": r["mapped"],
                 "match": r["match"]}
                for r in rows
            ],
        }
        if args.trap_catch_rate is not None:
            out["trap_catch_rate"] = args.trap_catch_rate
        write_json_atomic(args.out, out)
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: goldadd  (turn ONE human decision into a labeled gold example)
# --------------------------------------------------------------------------- #

GOLD_TRAP_TYPES = {"none", "hallucination", "pending_cite", "echo",
                   "lead_only", "off_topic", "poison"}
GOLD_HUMAN_LABELS = {"INCLUDE", "REVISE", "REJECT"}
GOLD_GATES = {"PASS_TO_PANEL", "BLOCKED", "DUP", "LEAD_ONLY", "REJECT"}
GOLD_FIELDS = ("candidate_id", "trap_type", "human_label", "expected_gate",
               "target_expert", "source_url", "author", "verbatim_quote",
               "source_text", "reason")


def _next_gold_id(items):
    """Next free gold-NNN id given the existing gold items (max+1, zero-padded)."""
    n = 0
    for it in items:
        cid = str(it.get("candidate_id", ""))
        if cid.startswith("gold-"):
            suf = cid[5:]
            if suf.isdigit():
                n = max(n, int(suf))
    return "gold-%03d" % (n + 1)


def _validate_gold_item(item):
    """Return a list of human-readable validation errors for one gold item ([] = ok)."""
    errs = []
    tt = item.get("trap_type")
    hl = item.get("human_label")
    if tt not in GOLD_TRAP_TYPES:
        errs.append("trap_type must be one of %s (got %r)" % (sorted(GOLD_TRAP_TYPES), tt))
    if hl not in GOLD_HUMAN_LABELS:
        errs.append("human_label must be one of %s (got %r)" % (sorted(GOLD_HUMAN_LABELS), hl))
    if not item.get("target_expert"):
        errs.append("target_expert is required")
    if not item.get("source_url"):
        errs.append("source_url is required")
    if not item.get("source_text"):
        errs.append("source_text is required (inline source body so goldcheck runs offline)")
    eg = item.get("expected_gate")
    if eg is not None and eg not in GOLD_GATES:
        errs.append("expected_gate, if given, must be one of %s (got %r)" % (sorted(GOLD_GATES), eg))
    return errs


def _gold_expected_gate(item, source_tiers, existing):
    """Deterministic expected_gate for `item`, replaying `existing` first so an
    echo/near-dup of an earlier same-expert PASS item resolves to DUP (mirrors
    goldcheck's ordering). Returns (gate, why)."""
    prior = {}
    for it in existing:
        out, _ = _gold_gate(it, source_tiers, prior)
        if out == "PASS_TO_PANEL":
            prior.setdefault(it.get("target_expert", ""), []).append(
                (content_hash(it.get("source_text", "")), minhash(it.get("source_text", ""))))
    return _gold_gate(item, source_tiers, prior)


def cmd_goldadd(args):
    """Validate ONE human-labeled candidate and append it to the gold set in the
    exact schema, computing expected_gate DETERMINISTICALLY (the gate's real
    outcome) so a hand-typed label can't drift the calibration. Used by the
    watch-review skill after a human INCLUDE/REVISE/REJECT decision; re-run
    goldcheck afterwards. Input as a JSON object via --item-file / --item-json /
    stdin (preferred for long source_text), or via individual flags."""
    if args.item_file:
        item = read_json(args.item_file, None)
    elif args.item_json:
        item = json.loads(args.item_json)
    elif args.item_stdin:
        item = json.loads(sys.stdin.read())
    else:
        item = {
            "trap_type": args.trap_type,
            "human_label": args.human_label,
            "target_expert": args.target_expert,
            "source_url": args.source_url,
            "author": args.author or "",
            "verbatim_quote": args.verbatim_quote or "",
            "source_text": args.source_text or "",
            "reason": args.reason or "",
        }
        if args.candidate_id:
            item["candidate_id"] = args.candidate_id
        if args.expected_gate:
            item["expected_gate"] = args.expected_gate
    if not isinstance(item, dict):
        eprint("goldadd: could not load a JSON object item (got %r)" % type(item).__name__)
        return 2

    item.setdefault("author", "")
    item.setdefault("verbatim_quote", "")
    item.setdefault("source_text", "")
    item.setdefault("reason", "")

    errs = _validate_gold_item(item)
    if errs:
        for e in errs:
            eprint("  - " + e)
        eprint("goldadd: validation FAILED (nothing written)")
        return 2

    st = read_json(args.source_tiers, {})
    existing = read_jsonl(args.goldset)
    ids = {str(it.get("candidate_id")) for it in existing}
    cid = item.get("candidate_id")
    if not cid:
        cid = _next_gold_id(existing)
    elif cid in ids:
        eprint("goldadd: candidate_id %s already exists in %s (nothing written)" % (cid, args.goldset))
        return 2
    item["candidate_id"] = cid

    computed, why = _gold_expected_gate(item, st, existing)
    given = item.get("expected_gate")
    if given and given != computed:
        if not args.force:
            eprint("goldadd: expected_gate mismatch - you wrote %r but the deterministic gates "
                   "produce %r (%s)." % (given, computed, why))
            eprint("         The gold set records what the GATES actually do; fix the item, or "
                   "pass --force to override (rare).")
            return 2
        aprint("goldadd: WARN overriding deterministic gate %r with provided %r (--force)" % (computed, given))
        computed = given

    rec = {
        "candidate_id": cid,
        "trap_type": item.get("trap_type"),
        "human_label": item.get("human_label"),
        "expected_gate": computed,
        "target_expert": item.get("target_expert"),
        "source_url": item.get("source_url"),
        "author": item.get("author", ""),
        "verbatim_quote": item.get("verbatim_quote", ""),
        "source_text": item.get("source_text", ""),
        "reason": item.get("reason", ""),
    }

    if args.dry_run:
        aprint("goldadd DRY-RUN: would append %s (expected_gate=%s; %s)" % (cid, computed, why))
        aprint(json.dumps(rec, ensure_ascii=False))
        return 0

    append_jsonl(args.goldset, rec)
    aprint("goldadd: appended %s to %s (trap=%s, human=%s, expected_gate=%s)"
           % (cid, args.goldset, rec["trap_type"], rec["human_label"], computed))
    aprint("goldadd: now re-run goldcheck to confirm the gates still pass:")
    aprint("  python watch_lib.py goldcheck --goldset %s --source-tiers %s"
           % (args.goldset, args.source_tiers))
    return 0


def cmd_canon_url(args):
    aprint(canonicalize_url(args.url))
    return 0


def cmd_fingerprint(args):
    text = sys.stdin.read()
    aprint(json.dumps(minhash(text)))
    return 0


# --------------------------------------------------------------------------- #
# Subcommand: selftest  (NO network - proves the safety-critical gates)
# --------------------------------------------------------------------------- #

def cmd_selftest(args):
    failures = []
    total = [0]

    def check(name, cond):
        total[0] += 1
        if cond:
            aprint("  ok   " + name)
        else:
            aprint("  FAIL " + name)
            failures.append(name)

    aprint("watch_lib selftest")

    # --- URL canonicalization ---
    check("canon strips utm + www + trailing slash + http->https",
          canonicalize_url("http://www.Example.com/Post/?utm_source=x&b=2&a=1#frag")
          == "https://example.com/Post?a=1&b=2")
    check("canon http and https collapse",
          canonicalize_url("http://x.com/a") == canonicalize_url("https://x.com/a"))

    # --- visible-text extraction ---
    html = b"<html><head><style>.x{}</style></head><body><script>var a=1</script>" \
           b"<h1>Hello</h1><p>World &amp; peace</p></body></html>"
    vt = extract_visible_text(html)
    check("extract strips script/style, keeps text, unescapes",
          "Hello World & peace" in vt and "var a" not in vt and ".x" not in vt)

    # --- content hash stable across irrelevant tag noise ---
    h1 = content_hash("<p>Same idea here</p>")
    h2 = content_hash("<p id='123' data-ts='999'>Same   idea here</p>")
    check("content_hash stable across whitespace/attr noise", h1 == h2)

    # --- GATE C: verbatim quote faithfulness (the loop-closer) ---
    source = "The model should write loops, not code. That is the real job."
    check("quote present -> True",
          verify_quote_substring("The model should write loops", source) is True)
    check("quote present despite whitespace diff -> True",
          verify_quote_substring("write   loops,    not code", source) is True)
    check("smart-quote source vs straight-quote claim -> True",
          verify_quote_substring("it's the job",
                                 "Well, it’s the job, really") is True)
    check("HALLUCINATED quote -> False (BLOCKED)",
          verify_quote_substring("write unit tests for everything", source) is False)
    check("empty quote -> False", verify_quote_substring("", source) is False)

    # --- MinHash dedup ---
    a = "Agentic coding works best when you let the model run a tight verify loop and iterate."
    b = "Agentic coding works best when you let the model run a tight verify loop and iterate fast."
    c = "Sponsorship rate cards for faceless TikTok accounts depend on engagement not followers."
    check("near-identical texts flagged near-dup", is_near_dup(minhash(a), minhash(b)))
    check("unrelated texts NOT near-dup", not is_near_dup(minhash(a), minhash(c)))

    # --- GATE A: tier assignment ---
    st = {
        "tiers": {
            "0": {"domains": ["anthropic.com", "code.claude.com"], "authors": []},
            "1": {"domains": ["simonwillison.net"], "authors": ["Andrej Karpathy"]},
        },
        "reject_domains": ["contentfarm.example"],
    }
    check("tier0 official domain", assign_tier("https://www.anthropic.com/engineering/x", "", st) == 0)
    check("tier0 subdomain suffix match",
          assign_tier("https://docs.anthropic.com/whatever", "", st) == 0)
    check("tier1 named practitioner domain",
          assign_tier("https://simonwillison.net/2026/x", "", st) == 1)
    check("tier1 by author on shared platform",
          assign_tier("https://medium.com/@k/post", "Andrej Karpathy", st) == 1)
    check("unknown domain -> default tier 3 (lead-only)",
          assign_tier("https://random-new-blog.example/p", "", st) == 3)
    check("reject-listed domain -> X",
          assign_tier("https://contentfarm.example/p", "", st) == "X")

    # --- Router (the QUEUE/REJECT/AUTO decision) ---
    def cand(**kw):
        base = {
            "source": {"url": "https://www.anthropic.com/news/x", "tier": 0,
                       "fetch_status": "vendored"},
            "target_expert": "boris",
            "claims": [{"confidence_flag": "verbatim", "quote": "q", "quote_present": True}],
            "gate": {"faithfulness_pass": True, "novelty_pass": True,
                     "relevance_pass": True, "contradiction": False},
            "panel": {"verdict": "GO", "borderline": False, "margin": 4},
        }
        for k, v in kw.items():
            if k in ("source", "gate", "panel"):
                base[k].update(v)
            else:
                base[k] = v
        return base

    check("auto-lane OFF -> QUEUE even for perfect tier-0",
          route_candidate(cand(), auto_lane="off")["decision"] == "QUEUE")
    check("auto-lane tier0 + calibration green -> AUTO_INTEGRATE",
          route_candidate(cand(), auto_lane="tier0", calibration_green=True)["decision"]
          == "AUTO_INTEGRATE")
    check("calibration NOT green -> QUEUE",
          route_candidate(cand(), auto_lane="tier0", calibration_green=False)["decision"]
          == "QUEUE")
    check("faithfulness fail -> REJECT",
          route_candidate(cand(gate={"faithfulness_pass": False}), auto_lane="tier0",
                          calibration_green=True)["decision"] == "REJECT")
    check("not vendored -> REJECT",
          route_candidate(cand(source={"fetch_status": "pending"}))["decision"] == "REJECT")
    check("tier X -> REJECT",
          route_candidate(cand(source={"tier": "X"}))["decision"] == "REJECT")
    check("duplicate (novelty fail) -> REJECT",
          route_candidate(cand(gate={"novelty_pass": False}))["decision"] == "REJECT")
    check("contradiction -> QUEUE (human review) even with auto-lane",
          route_candidate(cand(gate={"contradiction": True}), auto_lane="tier0",
                          calibration_green=True)["decision"] == "QUEUE")
    check("panel NO_GO -> REJECT",
          route_candidate(cand(panel={"verdict": "NO_GO"}))["decision"] == "REJECT")
    check("borderline panel -> QUEUE (no auto margin)",
          route_candidate(cand(panel={"borderline": True}), auto_lane="tier0",
                          calibration_green=True)["decision"] == "QUEUE")
    check("tier1 cannot use tier0 auto-lane -> QUEUE",
          route_candidate(cand(source={"tier": 1}), auto_lane="tier0",
                          calibration_green=True)["decision"] == "QUEUE")

    # --- goldadd: id assignment, schema validation, deterministic expected_gate ---
    check("next gold id on empty set -> gold-001", _next_gold_id([]) == "gold-001")
    check("next gold id is max+1 (unordered, padded)",
          _next_gold_id([{"candidate_id": "gold-003"}, {"candidate_id": "gold-001"}]) == "gold-004")
    check("validate flags bad trap_type + missing source_text",
          len(_validate_gold_item({"trap_type": "bogus", "human_label": "INCLUDE",
                                   "target_expert": "boris", "source_url": "u"})) >= 2)
    check("validate passes a well-formed item",
          _validate_gold_item({"trap_type": "none", "human_label": "INCLUDE",
                               "target_expert": "boris", "source_url": "https://x",
                               "source_text": "body"}) == [])
    gold_src = "The model should write loops, not code. That is the real job, really."
    check("goldadd expected_gate: faithful tier0 quote -> PASS_TO_PANEL",
          _gold_expected_gate({"source_url": "https://www.anthropic.com/x", "author": "",
                               "verbatim_quote": "write loops", "source_text": gold_src,
                               "target_expert": "boris"}, st, [])[0] == "PASS_TO_PANEL")
    check("goldadd expected_gate: hallucinated quote -> BLOCKED",
          _gold_expected_gate({"source_url": "https://www.anthropic.com/x", "author": "",
                               "verbatim_quote": "write unit tests for everything",
                               "source_text": gold_src, "target_expert": "boris"}, st, [])[0] == "BLOCKED")

    aprint("")
    if failures:
        aprint("SELFTEST FAILED: %d of %d checks failed" % (len(failures), total[0]))
        return 1
    aprint("SELFTEST PASSED: %d checks" % total[0])
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(description="Deterministic engine for the library currency-watch pipeline.")
    sub = p.add_subparsers(dest="cmd")

    m = sub.add_parser("migrate-meta", help="add last_checked + newest_content_date to every _meta.json")
    m.add_argument("--root", required=True, help="library root dir")
    m.add_argument("--today", required=True, help="date to seed when last_updated is absent (YYYY-MM-DD)")
    m.add_argument("--apply", action="store_true", help="write changes (default: dry-run)")
    m.add_argument("--verbose", action="store_true")
    m.set_defaults(func=cmd_migrate_meta)

    v = sub.add_parser("verify-quotes", help="deterministic faithfulness gate on model proposals")
    v.add_argument("--proposals", required=True)
    v.add_argument("--out", required=True)
    v.set_defaults(func=cmd_verify_quotes)

    r = sub.add_parser("route", help="apply thresholds -> AUTO_INTEGRATE|QUEUE|REJECT")
    r.add_argument("--proposals", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--auto-lane", default="off", choices=["off", "tier0"])
    r.add_argument("--calibration-green", action="store_true")
    r.add_argument("--per-domain-cap", type=int, default=3)
    r.set_defaults(func=cmd_route)

    g = sub.add_parser("digest", help="write the human review digest")
    g.add_argument("--decisions", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--run-id", default="")
    g.add_argument("--library", default="")
    g.add_argument("--include-rejects", action="store_true")
    g.set_defaults(func=cmd_digest)

    cu = sub.add_parser("canon-url")
    cu.add_argument("url")
    cu.set_defaults(func=cmd_canon_url)

    fp = sub.add_parser("fingerprint", help="MinHash of stdin text")
    fp.set_defaults(func=cmd_fingerprint)

    st = sub.add_parser("selftest", help="run built-in unit checks (no network)")
    st.set_defaults(func=cmd_selftest)

    gc = sub.add_parser("goldcheck", help="replay the gold set through the deterministic gates")
    gc.add_argument("--goldset", required=True)
    gc.add_argument("--source-tiers", required=True)
    gc.add_argument("--out", default=None, help="optional calibration JSON to write")
    gc.set_defaults(func=cmd_goldcheck)

    gpn = sub.add_parser("goldpanel", help="ADVISORY: council-verdict vs gold-label agreement on panel-only items (never gates)")
    gpn.add_argument("--goldset", required=True)
    gpn.add_argument("--verdicts", required=True, help="JSON map candidate_id -> curation_verdict object OR bare verdict string")
    gpn.add_argument("--out", default=None, help="optional JSON to write (agreement + detail) for run-health")
    gpn.add_argument("--trap-catch-rate", dest="trap_catch_rate", type=float, default=None,
                     help="optional; carried into --out so a downstream consumer reads both numbers from one file")
    gpn.set_defaults(func=cmd_goldpanel)

    ga = sub.add_parser("goldadd", help="validate + append ONE human-labeled candidate to the gold set")
    ga.add_argument("--goldset", required=True)
    ga.add_argument("--source-tiers", required=True)
    ga.add_argument("--item-file", default="", help="JSON file with the item object (preferred for long source_text)")
    ga.add_argument("--item-json", default="", help="the item as an inline JSON string")
    ga.add_argument("--item-stdin", action="store_true", help="read the item JSON object from stdin")
    ga.add_argument("--candidate-id", default="", help="override id (default: next gold-NNN)")
    ga.add_argument("--trap-type", default="", choices=[""] + sorted(GOLD_TRAP_TYPES))
    ga.add_argument("--human-label", default="", choices=[""] + sorted(GOLD_HUMAN_LABELS))
    ga.add_argument("--expected-gate", default="", choices=[""] + sorted(GOLD_GATES),
                    help="optional; verified against the deterministic gate (use --force to override)")
    ga.add_argument("--target-expert", default="")
    ga.add_argument("--source-url", default="")
    ga.add_argument("--author", default="")
    ga.add_argument("--verbatim-quote", default="")
    ga.add_argument("--source-text", default="")
    ga.add_argument("--reason", default="")
    ga.add_argument("--force", action="store_true", help="override an expected_gate that disagrees with the gates")
    ga.add_argument("--dry-run", action="store_true", help="validate + show the record, write nothing")
    ga.set_defaults(func=cmd_goldadd)

    rs = sub.add_parser("resolve-sources", help="expand a library's watch.json sources (no network)")
    rs.add_argument("--library-dir", required=True)
    rs.add_argument("--watchlist", required=True)
    rs.add_argument("--out", default=None)
    rs.set_defaults(func=cmd_resolve_sources)

    cm = sub.add_parser("commit", help="append _seen + bump _meta dates after a run (atomic)")
    cm.add_argument("--library-dir", required=True)
    cm.add_argument("--decisions", required=True)
    cm.add_argument("--run-id", required=True)
    cm.add_argument("--today", required=True)
    cm.set_defaults(func=cmd_commit)

    pp = sub.add_parser("postpass", help="full deterministic post-pass for one library")
    pp.add_argument("--library-dir", required=True)
    pp.add_argument("--proposals", required=True)
    pp.add_argument("--source-tiers", required=True)
    pp.add_argument("--vendor-script", default="")
    pp.add_argument("--no-vendor", action="store_true", help="skip the vendor_source.ps1 integrity fetch (offline tests)")
    pp.add_argument("--run-id", required=True)
    pp.add_argument("--today", required=True)
    pp.add_argument("--digest", required=True)
    pp.add_argument("--runhealth", required=True)
    pp.add_argument("--decisions-out", default=None)
    pp.add_argument("--auto-lane", default="off", choices=["off", "tier0"])
    pp.add_argument("--calibration-green", action="store_true")
    pp.add_argument("--per-domain-cap", type=int, default=3)
    pp.add_argument("--include-rejects", action="store_true")
    pp.add_argument("--gold", default=None,
                    help="path to a goldpanel --out JSON; if present its agreement/trap_catch_rate are surfaced into run-health")
    pp.set_defaults(func=cmd_postpass)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
