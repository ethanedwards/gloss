from bs4 import BeautifulSoup, Tag

def process_html(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all word-group divs
    word_groups = soup.find_all('div', class_='word-group')

    i = 0
    while i < len(word_groups):
        group = word_groups[i]
        word = group.find('div', class_='word')
        if word:
            text = word.contents[0].strip()
            
            # Check if it's a character name (all caps)
            if text.isupper() and text.endswith('.'):
                # Remove gloss for character names
                gloss = word.find('div', class_='gloss')
                if gloss:
                    gloss.decompose()
                
                # Merge with the next word-group if it exists
                if i + 1 < len(word_groups):
                    next_group = word_groups[i+1]
                    # Move all children of next_group to the current group
                    for child in list(next_group.children):
                        if isinstance(child, Tag):
                            group.append(child)
                    # Remove the now-empty next_group
                    next_group.decompose()
                    # Skip the next iteration since we've merged it
                    i += 1
        i += 1

    # Convert the modified soup back to a string
    modified_html = str(soup)

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(modified_html)

# Example usage
input_file = 'templates/ibsenold.html'  # Replace with your input HTML file path
output_file = 'templates/ibsenold2.html'  # Replace with your desired output HTML file path

process_html(input_file, output_file)
