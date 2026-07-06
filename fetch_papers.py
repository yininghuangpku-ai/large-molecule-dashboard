import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

def search_pubmed(query, max_results=20):
    """Search PubMed and return paper details."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    # Calculate date range (last 14 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=14)
    mindate = start_date.strftime("%Y/%m/%d")
    maxdate = end_date.strftime("%Y/%m/%d")
    
    # Search for paper IDs
    search_params = urllib.parse.urlencode({
        'db': 'pubmed',
        'term': query,
        'retmax': max_results,
        'datetype': 'pdat',
        'mindate': mindate,
        'maxdate': maxdate,
        'sort': 'date',
        'retmode': 'xml'
    })
    
    search_url = f"{base_url}esearch.fcgi?{search_params}"
    
    try:
        with urllib.request.urlopen(search_url) as response:
            search_tree = ET.parse(response)
            search_root = search_tree.getroot()
    except Exception as e:
        print(f"Search error for query '{query}': {e}")
        return []
    
    id_list = search_root.findall('.//Id')
    if not id_list:
        return []
    
    ids = ','.join([id_elem.text for id_elem in id_list])
    
    # Fetch paper details
    fetch_params = urllib.parse.urlencode({
        'db': 'pubmed',
        'id': ids,
        'retmode': 'xml'
    })
    
    fetch_url = f"{base_url}efetch.fcgi?{fetch_params}"
    
    try:
        with urllib.request.urlopen(fetch_url) as response:
            fetch_tree = ET.parse(response)
            fetch_root = fetch_tree.getroot()
    except Exception as e:
        print(f"Fetch error: {e}")
        return []
    
    papers = []
    for article in fetch_root.findall('.//PubmedArticle'):
        try:
            # Title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None and title_elem.text else "No title"
            
            # Authors
            authors_list = []
            for author in article.findall('.//Author')[:5]:
                lastname = author.find('LastName')
                forename = author.find('ForeName')
                if lastname is not None and lastname.text:
                    name = lastname.text
                    if forename is not None and forename.text:
                        name = f"{forename.text} {name}"
                    authors_list.append(name)
            authors = ', '.join(authors_list)
            if len(article.findall('.//Author')) > 5:
                authors += ' et al.'
            
            # Journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None and journal_elem.text else "Unknown Journal"
            
            # Date
            pub_date = article.find('.//PubDate')
            if pub_date is not None:
                year = pub_date.find('Year')
                month = pub_date.find('Month')
                day = pub_date.find('Day')
                date_str = ""
                if year is not None and year.text:
                    date_str = year.text
                if month is not None and month.text:
                    date_str = f"{month.text} {date_str}"
                if day is not None and day.text:
                    date_str = f"{date_str}-{day.text}"
                if not date_str:
                    date_str = "2024"
            else:
                date_str = "2024"
            
            # Abstract
            abstract_parts = article.findall('.//AbstractText')
            abstract = ' '.join([
                part.text for part in abstract_parts 
                if part.text
            ])[:500]
            if len(abstract) == 500:
                abstract += "..."
            
            # PMID for URL
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else ""
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "#"
            
            papers.append({
                'title': title,
                'authors': authors,
                'journal': journal,
                'date': date_str,
                'abstract': abstract,
                'url': url
            })
        except Exception as e:
            print(f"Error parsing article: {e}")
            continue
    
    return papers


def categorize_paper(paper):
    """Assign a category based on title and abstract content."""
    text = (paper['title'] + ' ' + paper.get('abstract', '')).lower()
    
    if any(kw in text for kw in ['mass spectrometry', 'ms/ms', 'lc-ms', 'maldi', 'intact mass', 'peptide mapping', 'bottom-up', 'top-down']):
        return 'Mass Spectrometry'
    elif any(kw in text for kw in ['glycosylation', 'glycan', 'glycoform', 'sialylation', 'fucosylation', 'n-glycan', 'o-glycan']):
        return 'Glycosylation'
    elif any(kw in text for kw in ['chromatography', 'hplc', 'sec', 'hic', 'cex', 'aex', 'rp-hplc', 'uplc', 'size exclusion']):
        return 'Chromatography'
    elif any(kw in text for kw in ['bioassay', 'cell-based assay', 'potency', 'biological activity', 'reporter gene']):
        return 'Bioassays'
    elif any(kw in text for kw in ['stability', 'degradation', 'forced degradation', 'accelerated', 'shelf life', 'aggregation']):
        return 'Stability'
    elif any(kw in text for kw in ['biosimilar', 'comparability', 'originator', 'interchangeable']):
        return 'Biosimilars'
    elif any(kw in text for kw in ['bispecific', 'adc', 'antibody-drug conjugate', 'fusion protein', 'nanobody', 'multispecific']):
        return 'Novel Modalities'
    else:
        return 'mAb Characterization'


def main():
    """Main function to fetch and compile papers."""
    
    # Define search queries for large molecule analytical development
    queries = {
        'monoclonal antibody characterization analytical': 8,
        'biotherapeutic mass spectrometry analysis': 6,
        'antibody glycosylation analysis': 5,
        'protein chromatography characterization biopharmaceutical': 5,
        'biologic drug stability analytical': 5,
        'biosimilar analytical characterization': 4,
        'bispecific antibody characterization': 4,
        'antibody-drug conjugate analytical': 4,
        'cell-based bioassay potency antibody': 4,
        'higher order structure therapeutic protein': 4,
        'charge variant analysis antibody': 3,
        'capillary electrophoresis biopharmaceutical': 3,
    }
    
    all_papers = []
    seen_titles = set()
    
    for query, max_results in queries.items():
        print(f"Searching: {query}")
        papers = search_pubmed(query, max_results)
        for paper in papers:
            # Deduplicate by title
            title_lower = paper['title'].lower().strip()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                paper['category'] = categorize_paper(paper)
                all_papers.append(paper)
    
    # Sort by date (most recent first)
    all_papers.sort(key=lambda x: x['date'], reverse=True)
    
    print(f"
Total unique papers found: {len(all_papers)}")
    
    # Save to JSON
    with open('papers.json', 'w', encoding='utf-8') as f:
        json.dump(all_papers, f, indent=2, ensure_ascii=False)
    
    print("Papers saved to papers.json")


if __name__ == '__main__':
    main()
