import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime, timedelta

def search_pubmed(query, max_results=5):
    """Search PubMed and return list of paper IDs."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "sort": "date",
        "retmode": "xml"
    }
    url = base_url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url) as response:
            tree = ET.parse(response)
            root = tree.getroot()
            id_list = root.find(".//IdList")
            if id_list is not None:
                return [id_elem.text for id_elem in id_list.findall("Id")]
    except Exception as e:
        print(f"Error searching PubMed: {e}")
    return []

def fetch_paper_details(paper_ids):
    """Fetch details for a list of PubMed IDs."""
    if not paper_ids:
        return []
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(paper_ids),
        "retmode": "xml"
    }
    url = base_url + "?" + urllib.parse.urlencode(params)
    papers = []
    try:
        with urllib.request.urlopen(url) as response:
            tree = ET.parse(response)
            root = tree.getroot()
            for article in root.findall(".//PubmedArticle"):
                paper = extract_paper_info(article)
                if paper:
                    papers.append(paper)
    except Exception as e:
        print(f"Error fetching details: {e}")
    return papers

def extract_paper_info(article):
    """Extract paper information from XML element."""
    try:
        medline = article.find(".//MedlineCitation")
        article_elem = medline.find(".//Article")
        title_elem = article_elem.find(".//ArticleTitle")
        title = title_elem.text if title_elem is not None and title_elem.text else "No title"
        abstract_elem = article_elem.find(".//Abstract/AbstractText")
        abstract = abstract_elem.text if abstract_elem is not None and abstract_elem.text else "No abstract available"
        authors = []
        author_list = article_elem.find(".//AuthorList")
        if author_list is not None:
            for author in author_list.findall("Author")[:3]:
                last = author.find("LastName")
                first = author.find("ForeName")
                if last is not None and last.text:
                    name = last.text
                    if first is not None and first.text:
                        name = first.text + " " + name
                    authors.append(name)
        pmid_elem = medline.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""
        journal_elem = article_elem.find(".//Journal/Title")
        journal = journal_elem.text if journal_elem is not None and journal_elem.text else "Unknown Journal"
        pub_date = ""
        date_elem = article_elem.find(".//Journal/JournalIssue/PubDate")
        if date_elem is not None:
            year = date_elem.find("Year")
            month = date_elem.find("Month")
            if year is not None and year.text:
                pub_date = year.text
                if month is not None and month.text:
                    pub_date = month.text + " " + pub_date
        return {
            "title": title,
            "authors": authors,
            "abstract": abstract[:300] + "..." if len(abstract) > 300 else abstract,
            "pmid": pmid,
            "journal": journal,
            "date": pub_date,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        }
    except Exception as e:
        print(f"Error extracting paper info: {e}")
        return None

def generate_html(all_papers):
    """Generate the HTML dashboard."""
    today = datetime.now().strftime("%B %d, %Y")
    html_start = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Large Molecule Analytical Development Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 50%, #0d2137 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            padding: 40px 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 2.2em;
            background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #94a3b8;
            font-size: 1.1em;
        }}
        .category-section {{
            margin-bottom: 40px;
        }}
        .category-title {{
            font-size: 1.5em;
            color: #60a5fa;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #1e3a5f;
        }}
        .papers-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }}
        .paper-card {{
            background: rgba(30, 58, 95, 0.5);
            border: 1px solid rgba(96, 165, 250, 0.2);
            border-radius: 12px;
            padding: 24px;
            transition: all 0.3s ease;
        }}
        .paper-card:hover {{
            transform: translateY(-3px);
            border-color: rgba(96, 165, 250, 0.5);
            box-shadow: 0 8px 25px rgba(96, 165, 250, 0.1);
        }}
        .paper-title {{
            font-size: 1.1em;
            color: #f1f5f9;
            margin-bottom: 10px;
            line-height: 1.4;
        }}
        .paper-title a {{
            color: #93c5fd;
            text-decoration: none;
        }}
        .paper-title a:hover {{
            text-decoration: underline;
        }}
        .paper-authors {{
            color: #94a3b8;
            font-size: 0.9em;
            margin-bottom: 8px;
        }}
        .paper-journal {{
            color: #a78bfa;
            font-size: 0.85em;
            margin-bottom: 10px;
        }}
        .paper-abstract {{
            color: #cbd5e1;
            font-size: 0.9em;
            line-height: 1.5;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .stat-box {{
            text-align: center;
            padding: 20px 30px;
            background: rgba(30, 58, 95, 0.5);
            border-radius: 12px;
            border: 1px solid rgba(96, 165, 250, 0.2);
        }}
        .stat-number {{
            font-size: 2em;
            color: #60a5fa;
            font-weight: bold;
        }}
        .stat-label {{
            color: #94a3b8;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .footer {{
            text-align: center;
            padding: 30px;
            color: #64748b;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Large Molecule Analytical Development & Characterization</h1>
        <p>Latest Research Papers - Updated {today}</p>
    </div>
'''

    total_papers = sum(len(papers) for papers in all_papers.values())
    num_categories = len(all_papers)

    html_stats = f'''    <div class="stats">
        <div class="stat-box">
            <div class="stat-number">{total_papers}</div>
            <div class="stat-label">Papers Found</div>
        </div>
        <div class="stat-box">
            <div class="stat-number">{num_categories}</div>
            <div class="stat-label">Research Categories</div>
        </div>
        <div class="stat-box">
            <div class="stat-number">{today}</div>
            <div class="stat-label">Last Updated</div>
        </div>
    </div>
'''

    html_content = ""
    for category, papers in all_papers.items():
        html_content += f'''    <div class="category-section">
        <h2 class="category-title">{category}</h2>
        <div class="papers-grid">
'''
        for paper in papers:
            authors_str = ", ".join(paper["authors"]) if paper["authors"] else "Unknown authors"
            safe_title = paper["title"].replace('"', '"')
            safe_abstract = paper["abstract"].replace('"', '"')
            html_content += f'''            <div class="paper-card">
                <div class="paper-title">
                    <a href="{paper["url"]}" target="_blank">{safe_title}</a>
                </div>
                <div class="paper-authors">{authors_str}</div>
                <div class="paper-journal">{paper["journal"]} | {paper["date"]}</div>
                <div class="paper-abstract">{safe_abstract}</div>
            </div>
'''
        html_content += '''        </div>
    </div>
'''

    html_end = '''    <div class="footer">
        <p>Data sourced from PubMed | Auto-updated weekly via GitHub Actions</p>
        <p>Dashboard for Large Molecule Analytical Development & Characterization Research</p>
    </div>
</body>
</html>'''

    return html_start + html_stats + html_content + html_end

def main():
    """Main function to fetch papers and generate dashboard."""
    search_categories = {
        "Antibody Characterization & Structure": "antibody characterization mass spectrometry structure 2024",
        "SEC-MALS & Size Analysis": "size exclusion chromatography multi-angle light scattering biotherapeutics 2024",
        "Charge Variant Analysis": "charge variant analysis capillary electrophoresis monoclonal antibody 2024",
        "Glycosylation Analysis": "glycosylation analysis biotherapeutic glycan characterization 2024",
        "Host Cell Protein Analysis": "host cell protein HCP analysis biopharmaceutical 2024",
        "Peptide Mapping & PTMs": "peptide mapping post-translational modifications therapeutic protein 2024",
        "Forced Degradation Studies": "forced degradation study biologic stability indicating 2024",
        "Biosimilar Analytical Comparability": "biosimilar analytical characterization comparability 2024"
    }

    print("Fetching latest research papers...")
    all_papers = {}
    for category, query in search_categories.items():
        print(f"  Searching: {category}")
        ids = search_pubmed(query, max_results=4)
        papers = fetch_paper_details(ids)
        if papers:
            all_papers[category] = papers
        import time
        time.sleep(1)

    if all_papers:
        html = generate_html(all_papers)
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Dashboard generated with {sum(len(p) for p in all_papers.values())} papers across {len(all_papers)} categories")
    else:
        print("No papers found. Keeping existing dashboard.")

if __name__ == "__main__":
    main()
