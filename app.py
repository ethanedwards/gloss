from flask import Flask, request, jsonify, render_template, Response
from textcreation.llm.claude import claude
from anthropic.types import ContentBlockDeltaEvent
import json

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
    
    def generate():
        for event in llm.get_completion_stream_sync(messages=messages):
            if isinstance(event, ContentBlockDeltaEvent):
                yield f"data: {json.dumps({'text': event.delta.text})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run()