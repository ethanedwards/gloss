from languages.german import German
from llm.claude import claude
import asyncio

async def test_steaming():
    ai = claude()
    messages = ai.format_messages(userprompt="What is a dog?")
    await ai.get_completion_stream_async(messages=messages, method=print)

def test_german():
    german = German()
    print(german.get_grammar("Hund", "Der Hund ist schnell.", 0))

#test_german()
asyncio.run(test_steaming())