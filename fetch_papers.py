import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import re
from datetime import datetime

# Category names MUST match the tab buttons in index.html exactly.
#
# We use PubMed only (arXiv is a physics/math/CS preprint server with no
# biopharmaceutical content). Every category query is built from THREE required
# parts so results are always about biologic-drug development, not the general
# science of the topic:
#     (TOPIC terms) AND (BIOLOGIC DRUG) AND (DRUG-DEVELOPMENT context)  NOT clinical
# All use PubMed [tiab] (Title/Abstract) field tags.

# Part 2 — the paper must concern a large-molecule DRUG, not a research reagent.
BIOLOGIC_DRUG = ('"monoclonal antibody"[tiab] OR "therapeutic antibody"[tiab] OR "therapeutic protein"[tiab] OR '
                 'biotherapeutic[tiab] OR biopharmaceutical[tiab] OR "protein therapeutic"[tiab] OR '
                 '"antibody-drug conjugate"[tiab] OR "Fc-fusion"[tiab] OR "therapeutic mAb"[tiab] OR '
                 'biologic[tiab] OR biologics[tiab]')

# Part 3 — the paper must sit in a drug-development / CMC / analytical context,
# which is what separates "glycosylation of a drug" from "glycosylation in disease".
DRUG_DEVELOPMENT = ('"quality attribute"[tiab] OR "critical quality attribute"[tiab] OR CMC[tiab] OR '
                    'manufacturing[tiab] OR biomanufacturing[tiab] OR "drug product"[tiab] OR '
                    '"drug substance"[tiab] OR bioprocess[tiab] OR "process development"[tiab] OR '
                    'formulation[tiab] OR comparability[tiab] OR "product quality"[tiab] OR '
                    '"analytical method"[tiab] OR "method development"[tiab] OR "method validation"[tiab] OR '
                    '"analytical characterization"[tiab] OR "release testing"[tiab] OR "quality control"[tiab] OR '
                    '"process characterization"[tiab] OR developability[tiab] OR "host cell protein"[tiab]')

# Part 4 — strip out clinical / disease / discovery / policy papers that reuse the vocabulary.
CLINICAL_EXCLUDE = (' NOT (patients[ti] OR "real-world"[tiab] OR efficacy[ti] OR "case reports"[pt] OR '
                    '"clinical trial"[pt] OR randomized[ti] OR vaccine[ti] OR disease[ti] OR diseases[ti] OR '
                    'diagnosis[ti] OR biomarker[ti] OR prognosis[ti] OR therapy[ti] OR treatment[ti] OR '
                    'switching[ti] OR affordability[tiab] OR reimbursement[tiab] OR pharmacokinetic*[ti])')

# Part 1 — the distinguishing TOPIC per category (technique or subject).
CATEGORY_TOPICS = {
    "mAb Characterization": ('"higher order structure"[tiab] OR "critical quality attribute"[tiab] OR '
                             '"charge variant"[tiab] OR "post-translational modification"[tiab] OR '
                             '"multi-attribute method"[tiab] OR "primary structure"[tiab] OR disulfide[tiab] OR '
                             '"physicochemical characterization"[tiab]'),
    "Mass Spectrometry": ('"mass spectrometry"[tiab] OR "LC-MS"[tiab] OR "native mass spectrometry"[tiab] OR '
                          '"peptide mapping"[tiab] OR "intact mass"[tiab] OR "hydrogen-deuterium exchange"[tiab]'),
    "Chromatography": ('"size exclusion chromatography"[tiab] OR "ion exchange chromatography"[tiab] OR '
                       '"reversed phase"[tiab] OR "hydrophobic interaction chromatography"[tiab] OR HPLC[tiab] OR '
                       'UHPLC[tiab] OR "capillary electrophoresis"[tiab]'),
    "Bioassays": ('"cell-based assay"[tiab] OR "reporter gene assay"[tiab] OR "potency assay"[tiab] OR '
                  '"relative potency"[tiab] OR "binding assay"[tiab] OR bioassay[tiab]'),
    "Glycosylation": ('glycosylation[tiab] OR glycan[tiab] OR glycoform[tiab] OR "N-glycan"[tiab] OR '
                      'sialylation[tiab] OR fucosylation[tiab] OR galactosylation[tiab]'),
    "Stability": ('aggregation[tiab] OR "forced degradation"[tiab] OR "subvisible particle"[tiab] OR '
                  'fragmentation[tiab] OR "stability-indicating"[tiab] OR "colloidal stability"[tiab] OR '
                  '"thermal stability"[tiab] OR deamidation[tiab] OR oxidation[tiab]'),
    "Biosimilars": ('biosimilar[tiab] OR "analytical similarity"[tiab] OR "analytical comparability"[tiab]'),
    "Novel Modalities": ('"antibody-drug conjugate"[tiab] OR ADC[tiab] OR "bispecific antibody"[tiab] OR '
                         '"Fc-fusion"[tiab] OR nanobody[tiab] OR multispecific[tiab] OR "drug-antibody ratio"[tiab]'),
}


def build_query(topic):
    """Combine the topic with the required drug-development context filters."""
    return (f"({topic}) AND ({BIOLOGIC_DRUG}) AND ({DRUG_DEVELOPMENT})" + CLINICAL_EXCLUDE)


CATEGORIES = {name: build_query(topic) for name, topic in CATEGORY_TOPICS.items()}

USER_AGENT = "LargeMoleculeDashboard/1.0 (https://github.com/yininghuangpku-ai/large-molecule-dashboard)"


def _get(url, timeout=30):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _clean(text):
    """Collapse whitespace/newlines into single spaces."""
    return re.sub(r"\s+", " ", (text or "").strip())


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

    for category, query in CATEGORIES.items():
        count_before = len(all_papers)
        results = fetch_pubmed(query, category, max_results=8)
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
