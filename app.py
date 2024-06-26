from flask import Flask, request, jsonify, render_template, Response
from textcreation.llm.claude import claude
from anthropic.types import ContentBlockDeltaEvent
import json

llm = claude()

app = Flask(__name__)

conversation_buffer = []

@app.route('/')
def index():
    return render_template('main.html')

@app.route('/inferno1')
def inferno1():
    return render_template('inferno1.html')

@app.route('/neele')
def neele():
    return render_template('neeleneele.html')

@app.route('/ibsen')
def ibsen():
    return render_template('ibsen.html')

@app.route('/lahiri')
def lahiri():
    return render_template('lahiri.html')



@app.route('/chatresponse', methods=['POST'])
def anthropic_proxy():
    global conversation_buffer

    systemprompt = """You are an assistant program for Gloss, an AI language tutoring system currently under development by Ethan Edwards. You are a tutor for the Italian language for students interested in reading literature, specifically Dante's Divine Comedy, the text you will be asked about. You explain in detail and handle special cases. Student questions will often ask about specific phrases, which you will be given the context of, including the results of an automatic grammatical parser.
    
    Students can access grammatical information by hovering over words, turn off the english gloss by hitting the 'a' key, and click on words to reveal their meanings once hidden. However you should keep your discussion to the text and language unless specifically asked about the interface."""
    
    request_data = request.get_json()
    prompt = request_data['content']
    
    # Add user prompt to the conversation buffer
    conversation_buffer.append({"role": "user", "content": prompt})
    
    #messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
    messages = llm.format_messages_buffer(buffer=conversation_buffer, systemprompt=systemprompt)
    print(messages)
    
    def generate():
        global conversation_buffer
        full_response = ""
        for event in llm.get_completion_stream_sync(messages=messages):
            if isinstance(event, ContentBlockDeltaEvent):
                full_response += event.delta.text
                yield f"data: {json.dumps({'text': event.delta.text})}\n\n"
        
        # After completion, add the full AI response to the conversation buffer
        conversation_buffer.append({"role": "assistant", "content": full_response})
        
        # Optionally, you can limit the buffer size to keep only recent messages
        if len(conversation_buffer) > 10:  # For example, keep only the last 10 messages
            conversation_buffer = conversation_buffer[-10:]
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/get_conversation', methods=['GET'])
def get_conversation():
    return jsonify(conversation_buffer)

if __name__ == '__main__':
    #app.run(debug=True, host='192.168.1.24')
    app.run()