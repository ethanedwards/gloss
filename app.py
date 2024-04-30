from flask import Flask, request, jsonify, render_template
from textcreation.llm.claude import claude
import requests

llm = claude()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chatresponse', methods=['POST'])
def anthropic_proxy():
    systemprompt = "You are an German tutor, who explains the language to learners interested in reading literature in the language. You assume your students are familiar with grammatical terms in general, though not specifically German. You explain in detail and handle special cases. Student questions will often ask about specific phrases, which you will be given the context of, including the results of an automatic grammatical parser."
    request_data = request.get_json()
    prompt = request_data['content']
    messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
    
    response = llm.get_completion_sync(messages=messages)
    print(response)
    return response

if __name__ == '__main__':
    app.run()