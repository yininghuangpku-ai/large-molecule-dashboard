import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import html
from datetime import datetime, timedelta

def fetch_arxiv_papers(query, max_results=5):
    base_url = "http://export.arxiv.org/api/query?"
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    url = base_url + urllib.parse.urlencode(params)
    papers = []
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "LargeMoleculeDashboard/1.0")
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read().decode("utf-8")
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            link_el = entry.find("atom:id", ns)
            authors = entry.findall("atom:author/atom:name", ns)
            title = title_el.text.strip().replace("
", " ") if title_el is not None else "No title"
            summary = summary_el.text.strip().replace("
", " ")[:200] if summary_el is not None else ""
            published = published_el.text[:10] if published_el is not None else ""
            link = link_el.text if link_el is not None else ""
            author_list = [a.text for a in authors[:3]]
            if len(authors) > 3:
                author_list.append("et al.")
            papers.append({
                "title": title,
                "authors": ", ".join(author_list),
                "date": published,
                "summary": summary,
                "link": link,
                "source": "arXiv"
            })
    except Exception as e:
        print(f"Error fetching from arXiv: {e}")
    return papers


def fetch_pubmed_papers(query, max_results=5):
    papers = []
    try:
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "sort": "date",
            "retmode": "json"
        }
        search_full_url = search_url + urllib.parse.urlencode(search_params)
        req = urllib.request.Request(search_full_url)
        req.add_header("User-Agent", "LargeMoleculeDashboard/1.0")
        with urllib.request.urlopen(req, timeout=30) as response:
            search_data = json.loads(response.read().decode("utf-8"))
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return papers
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json"
        }
        fetch_full_url = fetch_url + urllib.parse.urlencode(fetch_params)
        req2 = urllib.request.Request(fetch_full_url)
        req2.add_header("User-Agent", "LargeMoleculeDashboard/1.0")
        with urllib.request.urlopen(req2, timeout=30) as response:
            fetch_data = json.loads(response.read().decode("utf-8"))
        results = fetch_data.get("result", {})
        for pmid in id_list:
            article = results.get(pmid, {})
            if not isinstance(article, dict):
                continue
            title = article.get("title", "No title")
            authors_raw = article.get("authors", [])
            author_names = [a.get("name", "") for a in authors_raw[:3]]
            if len(authors_raw) > 3:
                author_names.append("et al.")
            pub_date = article.get("pubdate", "")
            link = "https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/"
            papers.append({
                "title": title,
                "authors": ", ".join(author_names),
                "date": pub_date,
                "summary": "",
                "link": link,
                "source": "PubMed"
            })
    except Exception as e:
        print(f"Error fetching from PubMed: {e}")
    return papers


def generate_html(all_papers):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Large Molecule Analytical Development Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; line-height: 1.6; }
        .header { background: linear-gradient(135deg, #1a237e 0%, #4a148c 100%); color: white; padding: 2rem; text-align: center; }
        .header h1 { font-size: 1.8rem; margin-bottom: 0.5rem; }
        .header p { opacity: 0.9; font-size: 0.95rem; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .category-section { margin-bottom: 2rem; }
        .category-title { font-size: 1.3rem; color: #1a237e; margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #1a237e; }
        .paper-card { background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: transform 0.2s; }
        .paper-card:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
        .paper-title { font-size: 1.05rem; font-weight: 600; color: #1a237e; margin-bottom: 0.5rem; }
        .paper-title a { color: inherit; text-decoration: none; }
        .paper-title a:hover { text-decoration: underline; }
        .paper-meta { font-size: 0.85rem; color: #666; margin-bottom: 0.5rem; }
        .paper-summary { font-size: 0.9rem; color: #555; }
        .source-badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; margin-right: 8px; }
        .source-arxiv { background: #fff3e0; color: #e65100; }
        .source-pubmed { background: #e8f5e9; color: #2e7d32; }
        .footer { text-align: center; padding: 2rem; color: #666; font-size: 0.85rem; }
        .no-papers { text-align: center; padding: 2rem; color: #999; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Large Molecule Analytical Development & Characterization</h1>
        <p>Latest Research Papers Dashboard</p>
        <p style="margin-top: 0.5rem; font-size: 0.85rem;">Last updated: """
    html += now
    html += """</p>
    </div>
    <div class="container">
"""

    for category, papers in all_papers.items():
        html += '        <div class="category-section">
'
        html += '            <h2 class="category-title">' + html_escape(category) + '</h2>
'
        if not papers:
            html += '            <p class="no-papers">No recent papers found.</p>
'
        else:
            for paper in papers:
                source_class = "source-arxiv" if paper["source"] == "arXiv" else "source-pubmed"
                html += '            <div class="paper-card">
'
                html += '                <div class="paper-title"><a href="' + html_escape(paper["link"]) + '" target="_blank">' + html_escape(paper["title"]) + '</a></div>
'
                html += '                <div class="paper-meta">
'
                html += '                    <span class="source-badge ' + source_class + '">' + html_escape(paper["source"]) + '</span>
'
                html += '                    ' + html_escape(paper["authors"]) + ' | ' + html_escape(paper["date"]) + '
'
                html += '                </div>
'
                if paper["summary"]:
                    html += '                <div class="paper-summary">' + html_escape(paper["summary"]) + '...</div>
'
                html += '            </div>
'
        html += '        </div>
'

    html += """    </div>
    <div class="footer">
        <p>Auto-updated weekly via GitHub Actions | Data from arXiv and PubMed</p>
    </div>
</body>
</html>"""
    return html


def html_escape(text):
    return html.escape(str(text))


def main():
    categories = {
        "Antibody Characterization & Higher-Order Structure": [
            ("arXiv", "antibody characterization higher order structure"),
            ("pubmed", "antibody characterization higher order structure analytical")
        ],
        "Mass Spectrometry for Biologics": [
            ("arXiv", "mass spectrometry biologics protein therapeutics"),
            ("pubmed", "mass spectrometry monoclonal antibody characterization")
        ],
        "Chromatography & Separation Science": [
            ("arXiv", "liquid chromatography protein separation biopharmaceutical"),
            ("pubmed", "chromatography biopharmaceutical protein analytical")
        ],
        "Biosimilar Analytical Assessment": [
            ("arXiv", "biosimilar analytical similarity assessment"),
            ("pubmed", "biosimilar analytical characterization comparability")
        ],
        "Post-Translational Modifications": [
            ("arXiv", "post translational modification therapeutic protein"),
            ("pubmed", "post-translational modifications biotherapeutics analytical")
        ]
    }

    all_papers = {}
    for category, queries in categories.items():
        papers = []
        for source, query in queries:
            if source == "arXiv":
                papers.extend(fetch_arxiv_papers(query, max_results=3))
            else:
                papers.extend(fetch_pubmed_papers(query, max_results=3))
        papers.sort(key=lambda x: x.get("date", ""), reverse=True)
        all_papers[category] = papers[:6]
        print(f"Fetched {len(papers)} papers for: {category}")

    html_content = generate_html(all_papers)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Dashboard updated successfully!")

    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(all_papers, f, indent=2, ensure_ascii=False)
    print("Papers data saved to papers.json")


if __name__ == "__main__":
    main()
