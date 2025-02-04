# app/routes/text_routes.py
from flask import Blueprint, render_template, jsonify, request
import json
import os
texts = Blueprint('texts', __name__)

# Dictionary to store text configurations
TEXT_CONFIG = {
    'inferno': {
        'pages': 1,  # number of pages
        'template_base': 'texts/inferno/inferno_{}.html',
        'sentence_store': 'texts/inferno/sentence_stores/inferno_{}.json'
    },
    'lahiri': {
        'pages': 18,
        'template_base': 'texts/lahiri/lahiri_{}.html',
        'sentence_store': 'texts/lahiri/sentence_stores/lahiri_{}.json'
    },
    'proust': {
        'pages': 1,
        'template_base': 'texts/proust/proust_{}.html',
        'sentence_store': 'texts/proust/sentence_stores/proust_{}.json'
    },
    'freude': {
        'pages': 1,
        'template_base': 'texts/freude/freude_{}.html',
        'sentence_store': 'texts/freude/sentence_stores/freude_{}.json'
    },
    'zarathustra': {
        'pages': 9,
        'template_base': 'texts/zarathustra/zarathustra_{}.html',
        'sentence_store': 'texts/zarathustra/sentence_stores/zarathustra_{}.json'
    },
    'sinocismtest': {
        'pages': 1,
        'template_base': 'texts/sinocismtest/sinocismtest_{}.html',
        'sentence_store': 'texts/sinocismtest/sentence_stores/sinocismtest_{}.json'
    },
    'persian_poems': {
        'pages': 1,
        'template_base': 'texts/persian_poems/persian_poems_{}.html',
        'sentence_store': 'texts/persian_poems/sentence_stores/persian_poems_{}.json'
    },
    # Add other texts...
}

@texts.route('/get_sentence_data')
def get_sentence_data():
    filename = request.args.get('filename')
    print(filename)
    # join all except the last element of the split
    text_name = '_'.join(filename.split('_')[:-1])
    print(text_name)
    # get the last element of the split
    page = filename.split('_')[-1]
    print(page)
    json_path = os.path.join(
        'app/templates/',  # Add templates directory to path
        TEXT_CONFIG[text_name]['sentence_store'].format(page)
    )
    with open(json_path, 'r') as f:
        sentence_data = json.load(f)
    return jsonify(sentence_data)

@texts.route('/<text_name>/<int:page>')
def show_text_page(text_name, page):
    print("Showing page " + str(page) + " of " + text_name)
    if text_name in TEXT_CONFIG:
        config = TEXT_CONFIG[text_name]
        if 1 <= page <= config['pages']:
            template = config['template_base'].format(page)
            return render_template(
                template,
                page=page,
                total_pages=config['pages'],
                text_name=text_name
            )
    return "Text or page not found", 404

def get_page_count(text_name):
    return TEXT_CONFIG[text_name]['pages']

