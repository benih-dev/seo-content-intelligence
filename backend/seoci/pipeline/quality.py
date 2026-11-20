import re
from urllib.parse import unquote, urljoin, urlparse

from seoci.export import markdown_headings
from seoci.urls import site_hostname

DIMENSIONS = ["Intent satisfaction", "Accuracy & evidence", "Original value", "Editorial quality",
              "On-page completeness", "Trust & accountability"]
WEIGHTS = {"blog_topic_fit": .25, "intent_fit": .20, "serp_attainability_gap": .20,
           "business_value": .15, "demand_signals": .10, "data_confidence": .10}


def opportunity(metrics, serp, keyword="", project=None, intent=None):
    available = metrics.get("volume") is not None
    project = project or {}
    tokens = set(re.findall(r"\w+", keyword.lower()))
    niche_tokens = set(re.findall(r"\w+", (project.get("niche", "") + " " + project.get("audience", "")).lower()))
    business_tokens = set(re.findall(r"\w+", project.get("business_objective", "").lower()))
    fit = len(tokens & niche_tokens) / max(1, len(tokens))
    business = len(tokens & business_tokens) / max(1, len(tokens))
    scores = {"blog_topic_fit": round(50 + 50 * fit), "intent_fit": 75 if intent == "informational" else 50,
              "serp_attainability_gap": 50 if serp else None,
              "business_value": round(50 + 50 * business), "demand_signals": min(100, metrics["volume"] / 100) if available else None,
              "data_confidence": 70 if available and serp else 30}
    reasons = {"blog_topic_fit": f"Keyword tokens overlapping niche/audience: {', '.join(sorted(tokens & niche_tokens)) or 'none; human fit review needed'}",
               "intent_fit": f"Intent {intent or 'unconfirmed'} compared with an educational blog format",
               "serp_attainability_gap": "Live snapshot exists; neutral starting score pending editorial competitor assessment",
               "business_value": f"Shared terms with project objective: {', '.join(sorted(tokens & business_tokens)) or 'none; value needs human confirmation'}",
               "demand_signals": "Provider volume scaled for internal prioritization; not a ranking estimate",
               "data_confidence": "Completeness of identified demand and live SERP data"}
    dims = {key: {"score": score, "weight": WEIGHTS[key], "reason": "Unavailable provider data" if score is None else
                  reasons[key], "confidence": .65 if key in {"demand_signals", "data_confidence"} and available and serp else .3}
            for key, score in scores.items()}
    total_weight = sum(WEIGHTS[k] for k, v in scores.items() if v is not None)
    return {"dimensions": dims, "score": round(sum(WEIGHTS[k] * v for k, v in scores.items() if v is not None) / total_weight, 1),
            "confidence": .65 if available and serp else .3, "not_a_ranking_prediction": True}


def overlap(keyword, inventory):
    tokens = set(re.findall(r"\w+", keyword.lower()))
    return [{"url": x.url, "reason": "Shared keyword/title/slug tokens; consider updating existing article",
             "recommendation": "update_existing_or_differentiate"} for x in inventory
            if len(tokens & set(re.findall(r"\w+", (x.title + " " + x.slug).lower()))) / max(1, len(tokens)) >= .5]


def _url_key(url):
    url = (url or "").strip()
    try:
        parts = urlparse(url)
        host = parts.hostname or ""
    except ValueError:
        return url.lower()
    return (host.removeprefix("www.") + parts.path.rstrip("/")).lower() + (f"?{parts.query}" if parts.query else "")


def _terms(text):
    return {x for x in re.findall(r"\w+", (text or "").lower()) if len(x) > 2}


def suggest_internal_links(inventory, topic, limit=5):
    """Rank inventory articles by shared topic terms; only real inventory URLs are returned."""
    terms = _terms(topic)
    ranked = []
    for item in inventory:
        shared = sorted(terms & _terms(f"{item.title} {item.slug}"))
        if shared:
            ranked.append((len(shared), item, shared))
    ranked.sort(key=lambda x: -x[0])
    return [{"url": item.url, "title": item.title, "anchor": item.title or item.slug, "status": "inventory",
             "reason": "Related article in your inventory; shares: " + ", ".join(shared)} for _, item, shared in ranked[:limit]]


def annotate_internal_links(links, inventory):
    """FR-023: links must come from the inventory; anything else is kept only as a search suggestion."""
    known = {_url_key(x.url): x for x in inventory}
    result, seen = [], set()
    for link in links:
        item = known.get(_url_key(link.get("url", ""))) if link.get("url") else None
        if item:
            entry = {"url": item.url, "title": item.title, "anchor": link.get("anchor") or item.title or item.slug,
                     "reason": link.get("reason") or "Selected from your inventory", "status": "inventory"}
        else:
            entry = {"url": link.get("url", ""), "title": link.get("title", ""), "anchor": link.get("anchor") or link.get("title") or link.get("url", ""),
                     "reason": "Not in your blog inventory: search for or publish a matching article before linking", "status": "search_suggestion"}
        key = _url_key(entry["url"]) or entry["anchor"].lower()
        if key not in seen:
            seen.add(key)
            result.append(entry)
    return result


def ymyl(keyword):
    return bool(re.search(r"\b(financ\w*|invest\w*|health|medic\w*|legal|safety|kesehatan|obat|hukum|keuangan|dana|tabungan|diet|penyakit|emergency fund)\b", keyword.lower()))


def url_key(url):
    parsed = urlparse(url)
    return site_hostname(parsed.hostname), unquote(parsed.path).rstrip("/") or "/"


def proposed_url(domain, slug):
    return urljoin(domain.rstrip("/") + "/", slug)


def available_slug(slug, domain, inventory):
    occupied = {url_key(url) for url in inventory}
    base = re.sub(r"[^a-z0-9]+", "-", unquote(urlparse(slug).path).lower()).strip("-") or "article"
    for index in range(len(occupied) + 1):
        candidate = base if index == 0 else f"{base}-{index + 1}"
        if url_key(proposed_url(domain, candidate)) not in occupied:
            return candidate
    raise RuntimeError("Could not allocate a unique article slug")


def publisher_label(value, recorded):
    if value.casefold() in {name.strip().casefold() for name in recorded if name}:
        return True
    if re.fullmatch(r"(?:https?://)?(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}/?", value, re.I):
        return True
    words = value.split()
    return 1 <= len(words) <= 6 and any(word[0].isupper() for word in words) and all(
        word in {"of", "the", "and", "for", "&", "di", "dan"}
        or re.fullmatch(r"[A-Z][A-Za-z'’&.-]*|\d+-[A-Z]+", word)
        for word in words)


def check_article(body, metadata, evidence, inventory, keyword, expert=False, project_domain=None):
    findings = []
    def add(dim, severity, location, finding, action):
        findings.append(dict(dimension=dim, severity=severity, location=location, finding=finding, action=action))
    source_urls = {x["url"] for x in evidence}
    for i, line in enumerate(body.splitlines(), 1):
        text = line
        reference = re.match(r"^\s*[-*+]\s+\[[^\]]+\]\((https?://[^)]+)\)", text)
        if reference and reference[1] in source_urls:
            text = text[reference.end():]
            tail = re.fullmatch(r"\s*[—–-]\s*([^;\n]+);\s*(?:retrieved|diakses)\s+\d{4}-\d{2}-\d{2}\s*", text, flags=re.I)
            if tail and publisher_label(tail[1].strip(), [ev.get("publisher") for ev in evidence if ev["url"] == reference[1]]):
                text = ""
        text = re.sub(r"https?://[^\s)]+", "", re.sub(r"^\d+\.\s", "", text))
        text = re.sub(r"^#{1,6}\s+(?:(?:step|langkah|tahap)\s+\d+(?:[:.)-]\s*|\s+|$)|\d+[.)]\s+)", "", text, flags=re.I)
        if re.search(r"\b\d+(?:[.,]\d+)?\s*(?:%|persen|percent|juta|million|days|hari|tahun|years)?", text):
            supported = any(ev.get("claim") and url in line and str(ev["claim"]) in line for ev in evidence for url in [ev["url"]])
            if not supported:
                add("Accuracy & evidence", "blocker", f"line:{i}", "Unsupported numeric claim", "Add evidence for this exact claim or remove it")
    headings = list(markdown_headings(body))
    previous = 0
    for line_number, level, _ in headings:
        if level > previous + 1:
            add("On-page completeness", "major", f"line:{line_number}", "Heading hierarchy skips a level", "Use sequential heading levels")
        previous = level
    if sum(level == 1 for _, level, _ in headings) != 1:
        add("On-page completeness", "major", "headings", "Expected exactly one H1", "Use one descriptive H1")
    if not 70 <= len(metadata.get("meta_description", "")) <= 160:
        add("On-page completeness", "major", "meta_description", "Meta description length outside editorial range", "Use a concise description of 70–160 characters")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata.get("slug", "")):
        add("On-page completeness", "major", "slug", "Invalid slug", "Use lowercase hyphen-separated words")
    known = set(inventory)
    known_keys = {url_key(url) for url in known}
    hosts = {host for host, _ in known_keys}
    if project_domain:
        hosts.add(site_hostname(urlparse(project_domain).hostname))
    domains = [project_domain] if project_domain else [f"{urlparse(url).scheme}://{urlparse(url).netloc}" for url in known]
    slug = metadata.get("slug", "")
    proposed = {url_key(proposed_url(domain, slug)) for domain in domains} if slug else set()
    if proposed & known_keys:
        add("On-page completeness", "major", "slug", "Slug collides with existing content", "Choose a unique path or update the existing article")
    for href in re.findall(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)", body):
        if href.startswith("#"):
            continue
        url = urljoin(proposed_url(domains[0], slug), href) if domains else href
        if urlparse(url).scheme not in {"http", "https"}:
            continue
        key = url_key(url)
        if key in proposed:
            add("On-page completeness", "major", href, "Self-referencing internal link", "Remove this link or choose a different article URL")
        if key[0] in hosts and key not in known_keys:
            add("On-page completeness", "major", url, "Unknown internal link", "Choose an existing inventory URL")
    words = body.split()
    if body.lower().count(keyword.lower()) * max(1, len(keyword.split())) / max(1, len(words)) > .07:
        add("Editorial quality", "major", "body", "Possible keyword stuffing", "Remove forced repetitions")
    if len(words) < 200:
        add("Original value", "blocker", "body", "Draft is too shallow to evaluate as a complete guide", "Develop the approved sections and examples")
    if expert:
        add("Trust & accountability", "blocker", "article", "Expert review required", "Provide explicit expert_reviewed approval after a qualified human review")
        if not any(ev.get("review_status") == "verified" for ev in evidence):
            add("Accuracy & evidence", "blocker", "sources", "YMYL sources need human verification", "Verify authoritative topic sources and record reviewer decision")
    return {"dimensions": DIMENSIONS, "findings": findings,
            "status": "blocked" if any(x["severity"] == "blocker" for x in findings) else "needs_revision" if any(x["severity"] == "major" for x in findings) else "pass",
            "expert_review_required": expert}
