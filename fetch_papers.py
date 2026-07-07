import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
from datetime import datetime

# Category names MUST match the tab buttons in index.html exactly.
# Each category maps to one or more (source, query) pairs.
CATEGORIES = {
    "mAb Characterization": [
        ("arxiv", "monoclonal antibody characterization higher order structure"),
        ("pubmed", "monoclonal antibody characterization analytical"),
    ],
    "Mass Spectrometry": [
        ("arxiv", "mass spectrometry protein therapeutics biologics"),
        ("pubmed", "mass spectrometry monoclonal antibody characterization"),
    ],
    "Chromatography": [
        ("arxiv", "liquid chromatography protein separation biopharmaceutical"),
        ("pubmed", "chromatography biopharmaceutical protein analytical"),
    ],
    "Bioassays": [
        ("pubmed", "bioassay potency biologics monoclonal antibody"),
    ],
    "Glycosylation": [
        ("pubmed", "glycosylation therapeutic antibody analytical"),
    ],
    "Stability": [
        ("pubmed", "stability aggregation therapeutic protein formulation"),
    ],
    "Biosimilars": [
        ("pubmed", "biosimilar analytical similarity comparability"),
    ],
    "Novel Modalities": [
        ("pubmed", "antibody drug conjugate bispecific characterization analytical"),
    ],
}

USER_AGENT = "LargeMoleculeDashboard/1.0 (https://github.com/yininghuangpku-ai/large-molecule-dashboard)"


def _get(url, timeout=30):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _clean(text):
    """Collapse whitespace/newlines into single spaces."""
    return re.sub(r"\s+", " ", (text or "").strip())


def fetch_arxiv(query, category, max_results=5):
    base_url = "http://export.arxiv.org/api/query?"
    params = {
        "search_query": "all:" + query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    url = base_url + urllib.parse.urlencode(params)
    papers = []
    try:
        data = _get(url)
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            link_el = entry.find("atom:id", ns)
            authors = entry.findall("atom:author/atom:name", ns)

            title = _clean(title_el.text) if title_el is not None else "No title"
            abstract = _clean(summary_el.text)[:350] if summary_el is not None else ""
            date = published_el.text[:10] if published_el is not None else ""
            url_link = link_el.text.strip() if link_el is not None else ""

            author_names = [_clean(a.text) for a in authors[:3]]
            if len(authors) > 3:
                author_names.append("et al.")

            papers.append({
                "title": title,
                "authors": ", ".join(author_names),
                "journal": "arXiv",
                "date": date,
                "abstract": abstract,
                "url": url_link,
                "category": category,
            })
    except Exception as e:
        print(f"  [arXiv] error for '{query}': {e}")
    return papers


def fetch_pubmed(query, category, max_results=5):
    papers = []
    try:
        # Step 1: search for PubMed IDs, most recent first.
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "sort": "date",
            "retmode": "json",
        })
        search_data = json.loads(_get(search_url))
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return papers

        # Step 2: fetch full records (title, abstract, authors, journal, date).
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
        })
        xml_data = _get(fetch_url)
        root = ET.fromstring(xml_data)

        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//MedlineCitation/PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            title_el = article.find(".//ArticleTitle")
            title = _clean("".join(title_el.itertext())) if title_el is not None else "No title"

            abstract_parts = [_clean("".join(a.itertext())) for a in article.findall(".//Abstract/AbstractText")]
            abstract = _clean(" ".join(abstract_parts))[:350]

            author_names = []
            for author in article.findall(".//AuthorList/Author"):
                last = author.find("LastName")
                initials = author.find("Initials")
                if last is not None:
                    name = last.text or ""
                    if initials is not None and initials.text:
                        name += " " + initials.text
                    author_names.append(_clean(name))
            display_authors = author_names[:3]
            if len(author_names) > 3:
                display_authors.append("et al.")

            journal_el = article.find(".//Journal/ISOAbbreviation")
            if journal_el is None:
                journal_el = article.find(".//Journal/Title")
            journal = _clean(journal_el.text) if journal_el is not None else "PubMed"

            date = _parse_pubmed_date(article)

            papers.append({
                "title": title,
                "authors": ", ".join(display_authors),
                "journal": journal,
                "date": date,
                "abstract": abstract,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "category": category,
            })
    except Exception as e:
        print(f"  [PubMed] error for '{query}': {e}")
    return papers


MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _parse_pubmed_date(article):
    """Return an ISO-ish YYYY-MM-DD date string (best effort) for sorting/display."""
    pubdate = article.find(".//Journal/JournalIssue/PubDate")
    if pubdate is None:
        pubdate = article.find(".//ArticleDate")
    if pubdate is None:
        return ""
    year = pubdate.findtext("Year", "")
    month = pubdate.findtext("Month", "")
    day = pubdate.findtext("Day", "")
    if month:
        month = MONTHS.get(month.strip().lower()[:3], month.zfill(2) if month.isdigit() else "01")
    else:
        month = "01"
    day = day.zfill(2) if day.isdigit() else "01"
    if not year:
        # Sometimes only a MedlineDate free-text string is present.
        medline = pubdate.findtext("MedlineDate", "")
        m = re.search(r"(\d{4})", medline)
        year = m.group(1) if m else ""
    if not year:
        return ""
    return f"{year}-{month}-{day}"


def main():
    all_papers = []
    seen = set()

    for category, sources in CATEGORIES.items():
        count_before = len(all_papers)
        for source, query in sources:
            if source == "arxiv":
                results = fetch_arxiv(query, category, max_results=4)
            else:
                results = fetch_pubmed(query, category, max_results=4)
            for paper in results:
                key = paper["title"].lower()[:80]
                if not paper["title"] or key in seen:
                    continue
                seen.add(key)
                all_papers.append(paper)
        print(f"{category}: +{len(all_papers) - count_before} papers")

    # Newest first. Empty dates sort to the bottom.
    all_papers.sort(key=lambda p: p.get("date") or "", reverse=True)

    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(all_papers, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(all_papers)} papers to papers.json")


if __name__ == "__main__":
    main()
