#Open file for reading
def process_file(input_file, output_file):
    with open(input_file, 'r') as file:
        content = file.read()

    processed_content = content.replace('\n\n', '__NEWLINE__').replace('\n', '').replace('__NEWLINE__', '\n\n')
    with open(output_file, 'w') as file:
        file.write(processed_content)

process_file('textcreation/texts/sources/marquezciench1.txt', 'textcreation/texts/sources/marquezciench1eng.txt')