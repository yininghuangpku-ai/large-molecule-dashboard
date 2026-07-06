import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime, timedelta

def search_pubmed(query, max_results=10):
    """Search PubMed and return list of paper IDs."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
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

def fetch_paper_details(pmids):
    """Fetch details for a list of PubMed IDs."""
    if not pmids:
        return []
    
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml"
    }
    url = base_url + "?" + urllib.parse.urlencode(params)
    
    papers = []
    try:
        with urllib.request.urlopen(url) as response:
            tree = ET.parse(response)
            root = tree.getroot()
            
            for article in root.findall(".//PubmedArticle"):
                try:
                    # Get title
                    title_elem = article.find(".//ArticleTitle")
                    title = title_elem.text if title_elem is not None and title_elem.text else "No title available"
                    
                    # Get authors
                    authors = []
                    author_list = article.find(".//AuthorList")
                    if author_list is not None:
                        for author in author_list.findall("Author"):
                            last_name = author.find("LastName")
                            fore_name = author.find("ForeName")
                            if last_name is not None and last_name.text:
                                name = last_name.text
                                if fore_name is not None and fore_name.text:
                                    name = fore_name.text + " " + name
                                authors.append(name)
                    
                    # Get journal
                    journal_elem = article.find(".//Journal/Title")
                    journal = journal_elem.text if journal_elem is not None and journal_elem.text else "Unknown Journal"
                    
                    # Get publication date
                    pub_date = ""
                    date_elem = article.find(".//PubDate")
                    if date_elem is not None:
                        year = date_elem.find("Year")
                        month = date_elem.find("Month")
                        if year is not None and year.text:
                            pub_date = year.text
                            if month is not None and month.text:
                                pub_date = month.text + " " + pub_date
                    
                    # Get abstract
                    abstract_elem = article.find(".//Abstract/AbstractText")
                    abstract = abstract_elem.text if abstract_elem is not None and abstract_elem.text else "No abstract available"
                    
                    # Get PMID
                    pmid_elem = article.find(".//PMID")
                    pmid = pmid_elem.text if pmid_elem is not None else ""
                    
                    papers.append({
                        "title": title,
                        "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                        "journal": journal,
                        "date": pub_date,
                        "abstract": abstract[:300] + "..." if len(abstract) > 300 else abstract,
                        "pmid": pmid,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                    })
                except Exception as e:
                    print(f"Error parsing article: {e}")
                    continue
    except Exception as e:
        print(f"Error fetching details: {e}")
    
    return papers

def generate_html(all_papers):
    """Generate the HTML dashboard."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Large Molecule Analytical Development Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 40px 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .header p {
            color: #888;
            font-size: 1.1em;
        }
        .category-section {
            margin-bottom: 40px;
        }
        .category-title {
            font-size: 1.5em;
            color: #00d2ff;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #3a7bd5;
        }
        .papers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }
        .paper-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .paper-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(0, 210, 255, 0.15);
            border-color: rgba(0, 210, 255, 0.3);
        }
        .paper-title {
            font-size: 1.05em;
            font-weight: 600;
            color: #fff;
            margin-bottom: 8px;
            line-height: 1.4;
        }
        .paper-title a {
            color: #fff;
            text-decoration: none;
        }
        .paper-title a:hover {
            color: #00d2ff;
        }
        .paper-authors {
            color: #aaa;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .paper-journal {
            color: #3a7bd5;
            font-size: 0.85em;
            font-style: italic;
            margin-bottom: 8px;
        }
        .paper-abstract {
            color: #999;
            font-size: 0.85em;
            line-height: 1.5;
        }
        .no-papers {
            color: #666;
            font-style: italic;
            padding: 20px;
        }
        @media (max-width: 768px) {
            .papers-grid {
                grid-template-columns: 1fr;
            }
            .header h1 { font-size: 1.8em; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Large Molecule Analytical Development & Characterization</h1>
        <p>Latest Research Papers | Auto-updated: """ + now + """</p>
    </div>
"""
    
    for category, papers in all_papers.items():
        html += f'    <div class="category-section">
'
        html += f'        <h2 class="category-title">{category}</h2>
'
        html += f'        <div class="papers-grid">
'
        
        if papers:
            for paper in papers:
                html += f'            <div class="paper-card">
'
                html += f'                <div class="paper-title"><a href="{paper["url"]}" target="_blank">{paper["title"]}</a></div>
'
                html += f'                <div class="paper-authors">{paper["authors"]}</div>
'
                html += f'                <div class="paper-journal">{paper["journal"]} | {paper["date"]}</div>
'
                html += f'                <div class="paper-abstract">{paper["abstract"]}</div>
'
                html += f'            </div>
'
        else:
            html += f'            <div class="no-papers">No recent papers found in this category.</div>
'
        
        html += f'        </div>
'
        html += f'    </div>
'
    
    html += """</body>
</html>"""
    
    return html

def main():
    # Define search categories relevant to large molecule analytical development
    categories = {
        "Monoclonal Antibody Characterization": "monoclonal antibody characterization analytical[Title/Abstract] AND 2024:2025[dp]",
        "Mass Spectrometry for Biologics": "(mass spectrometry biotherapeutics) OR (mass spectrometry antibody characterization) AND 2024:2025[dp]",
        "Size Exclusion Chromatography & Aggregation": "(size exclusion chromatography protein aggregation) OR (SEC-MALS biologics) AND 2024:2025[dp]",
        "Charge Variants & Ion Exchange": "(charge variant antibody) OR (ion exchange chromatography mAb) AND 2024:2025[dp]",
        "Glycosylation Analysis": "(glycosylation analysis antibody) OR (glycan characterization biologic) AND 2024:2025[dp]",
        "Higher Order Structure": "(higher order structure protein therapeutic) OR (HDX-MS antibody) AND 2024:2025[dp]",
        "Capillary Electrophoresis for Biologics": "(capillary electrophoresis antibody) OR (CE-SDS biologic) AND 2024:2025[dp]",
        "Forced Degradation & Stability": "(forced degradation biologic) OR (stability indicating method antibody) AND 2024:2025[dp]"
    }
    
    all_papers = {}
    
    for category, query in categories.items():
        print(f"Searching: {category}")
        pmids = search_pubmed(query, max_results=5)
        papers = fetch_paper_details(pmids)
        all_papers[category] = papers
        print(f"  Found {len(papers)} papers")
    
    # Generate HTML
    html_content = generate_html(all_papers)
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"
Dashboard generated successfully!")
    print(f"Total papers: {sum(len(p) for p in all_papers.values())}")

if __name__ == "__main__":
    main()
