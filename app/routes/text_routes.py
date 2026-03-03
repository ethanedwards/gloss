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
        'pages': 19,
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
        'pages': 2,
        'template_base': 'texts/persian_poems/persian_poems_{}.html',
        'sentence_store': 'texts/persian_poems/sentence_stores/persian_poems_{}.json'
    },
    'castlevania': {
        'pages': 4,
        'template_base': 'texts/castlevania/castlevania_{}.html',
        'sentence_store': 'texts/castlevania/sentence_stores/castlevania_{}.json'
    },
    'PI': {
        'pages': 8,
        'template_base': 'texts/PI/PI_{}.html',
        'sentence_store': 'texts/PI/sentence_stores/PI_{}.json'
    },
    'confessiones': {
        'pages': 2,
        'template_base': 'texts/confessiones/confessiones_{}.html',
        'sentence_store': 'texts/confessiones/sentence_stores/confessiones_{}.json'
    },
    'arsamatoria': {
        'pages': 1,
        'template_base': 'texts/arsamatoria/arsamatoria_{}.html',
        'sentence_store': 'texts/arsamatoria/sentence_stores/arsamatoria_{}.json'
    },
    'rood': {
        'pages': 1,
        'template_base': 'texts/rood/rood_{}.html',
        'sentence_store': 'texts/rood/sentence_stores/rood_{}.json'
    },
    'redchamber': {
        'pages': 99,
        'template_base': 'texts/redchamber/redchamber_{}.html',
        'sentence_store': 'texts/redchamber/sentence_stores/redchamber_{}.json'
    },
    'afsharitasnif': {
        'pages': 1,
        'template_base': 'texts/afsharitasnif/afsharitasnif_{}.html',
        'sentence_store': 'texts/afsharitasnif/sentence_stores/afsharitasnif_{}.json'
    },
    'ninesols': {
        'pages': 11,
        'template_base': 'texts/ninesols/ninesols_{}.html',
        'sentence_store': 'texts/ninesols/sentence_stores/ninesols_{}.json'
    },
    'labyrinth': {
        'pages': 10,
        'template_base': 'texts/labyrinth/labyrinth_{}.html',
        'sentence_store': 'texts/labyrinth/sentence_stores/labyrinth_{}.json'
    },
    'grandesertao': {
        'pages': 1,
        'template_base': 'texts/grandesertao/grandesertao_{}.html',
        'sentence_store': 'texts/grandesertao/sentence_stores/grandesertao_{}.json'
    },
    'ff6': {
        'pages': 80,
        'template_base': 'texts/ff6/ff6_{}.html',
        'sentence_store': 'texts/ff6/sentence_stores/ff6_{}.json'
    },
    'tangpoems': {
        'pages': 320,
        'template_base': 'texts/tangpoems/tangpoems_{}.html',
        'sentence_store': 'texts/tangpoems/sentence_stores/tangpoems_{}.json'
    },
    'melancholy': {
        'pages': 2,
        'template_base': 'texts/melancholy/melancholy_{}.html',
        'sentence_store': 'texts/melancholy/sentence_stores/melancholy_{}.json'
    },
    'mark': {
        'pages': 16,
        'template_base': 'texts/mark/mark_{}.html',
        'sentence_store': 'texts/mark/sentence_stores/mark_{}.json'
    },
    'matthew': {
        'pages': 12,
        'template_base': 'texts/matthew/matthew_{}.html',
        'sentence_store': 'texts/matthew/sentence_stores/matthew_{}.json'
    },
    'luke': {
        'pages': 2,
        'template_base': 'texts/luke/luke_{}.html',
        'sentence_store': 'texts/luke/sentence_stores/luke_{}.json'
    },
    'tractatus': {
        'pages': 7,
        'template_base': 'texts/tractatus/tractatus_{}.html',
        'sentence_store': 'texts/tractatus/sentence_stores/tractatus_{}.json'
    },
    'tractatus_new': {
        'pages': 7,
        'template_base': 'texts/tractatus_new/tractatus_{}.html',
        'sentence_store': 'texts/tractatus_new/sentence_stores/tractatus_{}.json'
    },
    'periodictable': {
        'pages': 22,
        'template_base': 'texts/periodictable/periodictable_{}.html',
        'sentence_store': 'texts/periodictable/sentence_stores/periodictable_{}.json'
    },
    "hazan": {
        'pages': 47,
        'template_base': 'texts/hazan/hazan_{}.html',
        'sentence_store': 'texts/hazan/sentence_stores/hazan_{}.json'
    },
    "perec": {
        'pages': 10,  # Will be updated after generation
        'template_base': 'texts/perec/perec_{}.html',
        'sentence_store': 'texts/perec/sentence_stores/perec_{}.json'
    },
    "rumi_jahan": {
        'pages': 1,
        'template_base': 'texts/rumi_jahan/rumi_jahan_{}.html',
        'sentence_store': 'texts/rumi_jahan/sentence_stores/rumi_jahan_{}.json'
    },
    "tahereh": {
        'pages': 2,
        'template_base': 'texts/tahereh/tahereh_{}.html',
        'sentence_store': 'texts/tahereh/sentence_stores/tahereh_{}.json'
    },
    "pierremenard": {
        'pages': 5,
        'template_base': 'texts/pierremenard/pierremenard_{}.html',
        'sentence_store': 'texts/pierremenard/sentence_stores/pierremenard_{}.json'
    },
    'mn2': {
        'pages': 2,
        'template_base': 'texts/mn2/mn2_{}.html',
        'sentence_store': 'texts/mn2/sentence_stores/mn2_{}.json'
    },
    'mn21': {
        'pages': 3,  # Will be updated after generation
        'template_base': 'texts/mn21/mn21_{}.html',
        'sentence_store': 'texts/mn21/sentence_stores/mn21_{}.json'
    }

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

