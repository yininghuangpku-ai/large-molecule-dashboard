import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime, timedelta

def fetch_pubmed_papers(query, max_results=20):
    """Fetch recent papers from PubMed."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    # Calculate date range (last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Search for papers
    search_params = urllib.parse.urlencode({
        'db': 'pubmed',
        'term': query,
        'retmax': max_results,
        'sort': 'date',
        'datetype': 'pdat',
        'mindate': start_date.strftime('%Y/%m/%d'),
        'maxdate': end_date.strftime('%Y/%m/%d'),
        'retmode': 'json'
    })
    
    search_url = f"{base_url}esearch.fcgi?{search_params}"
    
    try:
        with urllib.request.urlopen(search_url) as response:
            search_results = json.loads(response.read().decode())
    except Exception as e:
        print(f"Error searching PubMed: {e}")
        return []
    
    id_list = search_results.get('esearchresult', {}).get('idlist', [])
    
    if not id_list:
        print(f"No papers found for query: {query}")
        return []
    
    # Fetch paper details
    fetch_params = urllib.parse.urlencode({
        'db': 'pubmed',
        'id': ','.join(id_list),
        'retmode': 'xml'
    })
    
    fetch_url = f"{base_url}efetch.fcgi?{fetch_params}"
    
    try:
        with urllib.request.urlopen(fetch_url) as response:
            xml_data = response.read().decode()
    except Exception as e:
        print(f"Error fetching paper details: {e}")
        return []
    
    # Parse XML
    papers = []
    try:
        root = ET.fromstring(xml_data)
        for article in root.findall('.//PubmedArticle'):
            paper = parse_pubmed_article(article)
            if paper:
                papers.append(paper)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
    
    return papers

def parse_pubmed_article(article):
    """Parse a single PubMed article XML element."""
    try:
        # Get title
        title_elem = article.find('.//ArticleTitle')
        title = title_elem.text if title_elem is not None and title_elem.text else "No title available"
        
        # Get abstract
        abstract_parts = article.findall('.//Abstract/AbstractText')
        abstract = ' '.join([part.text for part in abstract_parts if part.text]) if abstract_parts else "No abstract available"
        
        # Get authors
        authors = []
        for author in article.findall('.//Author'):
            last_name = author.find('LastName')
            fore_name = author.find('ForeName')
            if last_name is not None and last_name.text:
                name = last_name.text
                if fore_name is not None and fore_name.text:
                    name = f"{fore_name.text} {name}"
                authors.append(name)
        
        # Get journal
        journal_elem = article.find('.//Journal/Title')
        journal = journal_elem.text if journal_elem is not None and journal_elem.text else "Unknown Journal"
        
        # Get publication date
        pub_date = article.find('.//PubDate')
        date_str = ""
        if pub_date is not None:
            year = pub_date.find('Year')
            month = pub_date.find('Month')
            day = pub_date.find('Day')
            if year is not None and year.text:
                date_str = year.text
                if month is not None and month.text:
                    date_str = f"{month.text} {date_str}"
                    if day is not None and day.text:
                        date_str = f"{day.text} {date_str}"
        
        # Get PMID
        pmid_elem = article.find('.//PMID')
        pmid = pmid_elem.text if pmid_elem is not None else ""
        
        # Get DOI
        doi = ""
        for id_elem in article.findall('.//ArticleId'):
            if id_elem.get('IdType') == 'doi':
                doi = id_elem.text
                break
        
        return {
            'title': title,
            'authors': ', '.join(authors[:5]) + ('...' if len(authors) > 5 else ''),
            'journal': journal,
            'date': date_str,
            'abstract': abstract[:300] + '...' if len(abstract) > 300 else abstract,
            'pmid': pmid,
            'doi': doi,
            'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        }
    except Exception as e:
        print(f"Error parsing article: {e}")
        return None

def generate_html(all_papers):
    """Generate the dashboard HTML file."""
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Large Molecule Analytical Development Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 50%, #0d2137 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 30px 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.2em;
            background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .header p {
            color: #94a3b8;
            font-size: 1.1em;
        }
        .update-info {
            text-align: center;
            color: #64748b;
            font-size: 0.9em;
            margin-bottom: 30px;
        }
        .category-section {
            margin-bottom: 40px;
        }
        .category-title {
            font-size: 1.5em;
            color: #60a5fa;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #1e3a5f;
        }
        .papers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }
        .paper-card {
            background: rgba(30, 58, 95, 0.5);
            border: 1px solid rgba(96, 165, 250, 0.2);
            border-radius: 12px;
            padding: 20px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .paper-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(96, 165, 250, 0.15);
            border-color: rgba(96, 165, 250, 0.4);
        }
        .paper-title {
            font-size: 1.05em;
            color: #e2e8f0;
            margin-bottom: 8px;
            line-height: 1.4;
        }
        .paper-title a {
            color: #93c5fd;
            text-decoration: none;
        }
        .paper-title a:hover {
            text-decoration: underline;
        }
        .paper-authors {
            color: #94a3b8;
            font-size: 0.85em;
            margin-bottom: 5px;
        }
        .paper-journal {
            color: #a78bfa;
            font-size: 0.85em;
            font-style: italic;
            margin-bottom: 5px;
        }
        .paper-date {
            color: #64748b;
            font-size: 0.8em;
            margin-bottom: 10px;
        }
        .paper-abstract {
            color: #b0bec5;
            font-size: 0.85em;
            line-height: 1.5;
        }
        .no-papers {
            color: #64748b;
            font-style: italic;
            padding: 20px;
        }
        @media (max-width: 768px) {
            .papers-grid {
                grid-template-columns: 1fr;
            }
            .header h1 { font-size: 1.6em; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Large Molecule Analytical Development & Characterization</h1>
        <p>Latest Research Papers Dashboard</p>
    </div>
    <div class="update-info">
        Last updated: """ + datetime.now().strftime('%B %d, %Y at %H:%M UTC') + """
    </div>
"""
    
    for category, papers in all_papers.items():
        html_content += f'    <div class="category-section">
'
        html_content += f'        <h2 class="category-title">{category}</h2>
'
        html_content += f'        <div class="papers-grid">
'
        
        if papers:
            for paper in papers:
                title_html = f'<a href="{paper["url"]}" target="_blank">{paper["title"]}</a>' if paper["url"] else paper["title"]
                html_content += f"""            <div class="paper-card">
                <div class="paper-title">{title_html}</div>
                <div class="paper-authors">{paper['authors']}</div>
                <div class="paper-journal">{paper['journal']}</div>
                <div class="paper-date">{paper['date']}</div>
                <div class="paper-abstract">{paper['abstract']}</div>
            </div>
"""
        else:
            html_content += '            <div class="no-papers">No recent papers found in this category.</div>
'
        
        html_content += '        </div>
'
        html_content += '    </div>
'
    
    html_content += """</body>
</html>"""
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Dashboard generated with {sum(len(p) for p in all_papers.values())} total papers")

def main():
    """Main function to fetch papers and generate dashboard."""
    
    # Define search categories relevant to large molecule analytical development
    search_queries = {
        "Antibody Characterization & Engineering": "antibody characterization OR antibody engineering OR monoclonal antibody analytics",
        "Mass Spectrometry for Biologics": "mass spectrometry biologics OR intact mass analysis protein OR peptide mapping therapeutic",
        "Chromatography Methods": "size exclusion chromatography protein OR ion exchange chromatography biologics OR HIC protein",
        "Higher Order Structure": "hydrogen deuterium exchange protein OR circular dichroism biologic OR protein higher order structure",
        "Glycosylation Analysis": "glycosylation analysis therapeutic protein OR glycan characterization antibody",
        "Forced Degradation & Stability": "forced degradation biologic OR protein stability analytical OR aggregation characterization protein",
        "Cell & Gene Therapy Analytics": "AAV characterization analytical OR gene therapy analytical development OR viral vector characterization"
    }
    
    all_papers = {}
    
    for category, query in search_queries.items():
        print(f"Fetching papers for: {category}")
        papers = fetch_pubmed_papers(query, max_results=5)
        all_papers[category] = papers
        print(f"  Found {len(papers)} papers")
    
    # Generate the HTML dashboard
    generate_html(all_papers)
    print("Dashboard update complete!")

if __name__ == "__main__":
    main()
