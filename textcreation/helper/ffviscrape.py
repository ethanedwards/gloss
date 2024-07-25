import requests
from bs4 import BeautifulSoup
import json
import re
import html

import re

def clean_text(text):
    # Remove HTML line breaks and extra whitespace
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def scrape_page(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    
    data = []
    
    # Find all relevant rows (narrate and dialogue)
    rows = soup.find_all('tr')
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 3:
            # Check if it's a narrate class or a dialogue
            if 'class' in row.attrs and 'narrate' in row['class']:
                source = clean_text(cells[1].text)
                translation = clean_text(cells[2].text)
            elif len(cells) == 4 and cells[0].text.strip() == '':
                source = clean_text(cells[1].text)
                translation = clean_text(cells[2].text)
            else:
                continue  # Skip rows that don't match our criteria
            
            if source and translation:
                # Remove character names from the beginning of dialogue, but keep content after 「
                source = re.sub(r'^([^：]+)：(?!「)', '', source)
                translation = re.sub(r'^([^:]+):\s*', '', translation)
                
                data.append({
                    "source": source.strip(),
                    "translation": translation.strip()
                })
    
    # Find the link to the next page
    next_link = soup.find('div', class_='next').find('a')
    next_url = next_link['href'] if next_link else None
    
    return data, next_url

def main():
    base_url = "https://kwhazit.ucoz.net/trans/ff6/"  # Replace with the actual base URL
    current_url = base_url + "01intro.html"
    all_data = []

    while current_url:
        print(f"Scraping: {current_url}")
        page_data, next_url = scrape_page(current_url)
        all_data.extend(page_data)
        
        if next_url and next_url != "index.html":
            current_url = base_url + next_url
        else:
            break

    # Save to JSON file
    with open('ff6_translations.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"Scraping complete. Data saved to ff6_translations.json")

if __name__ == "__main__":
    main()