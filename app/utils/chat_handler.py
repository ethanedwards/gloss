# app/utils/chat_handler.py
from flask import Response
import json
from textcreation.llm.claude import claude
from anthropic.types import ContentBlockDeltaEvent
from textcreation.promptlibrary import promptlibrary

class ChatHandler:
    def __init__(self):
        self.llm = claude()
        self.conversation_buffer = []
        self.prompt_library = promptlibrary("textcreation/promptlibrary.yml")
        self.system_prompt = """You are an assistant program for Gloss, an AI language tutoring system currently under development by Ethan Edwards. You are a tutor for the Italian language for students interested in reading literature, specifically Dante's Divine Comedy, the text you will be asked about. You explain in detail and handle special cases. Student questions will often ask about specific phrases, which you will be given the context of, including the results of an automatic grammatical parser.
        
        Students can access grammatical information by hovering over words, turn off the english gloss by hitting the 'a' key, and click on words to reveal their meanings once hidden. However you should keep your discussion to the text and language unless specifically asked about the interface."""

    def generate_response(self, messages):
        full_response = ""
        for event in self.llm.get_completion_stream_sync(messages=messages):
            if isinstance(event, ContentBlockDeltaEvent):
                full_response += event.delta.text
                yield f"data: {json.dumps({'text': event.delta.text})}\n\n"
        
        self.conversation_buffer.append({"role": "assistant", "content": full_response})
        
        if len(self.conversation_buffer) > 10:
            self.conversation_buffer = self.conversation_buffer[-10:]

    def handle_chat(self, request_data, textname):
        prompt = request_data['content']

        system_prompt = self.prompt_library.find_prompt_by_title(prompt_dict[textname])

        self.conversation_buffer.append({"role": "user", "content": prompt})
        
        messages = self.llm.format_messages_buffer(
            buffer=self.conversation_buffer, 
            systemprompt=system_prompt
        )
        
        return Response(
            self.generate_response(messages), 
            mimetype='text/event-stream'
        )

    def get_conversation(self):
        return self.conversation_buffer
    

prompt_dict = {
    'lahiri': 'ChatLahiri',
    'inferno': 'ChatInferno',
    'freude': 'ChatFreude',
    'zarathustra': 'ChatZarathustra',
    'sinocismtest': 'ChatChinese',
    'persian_poems': 'ChatPersianPoems',
    'castlevania': 'ChatCastlevania'
}