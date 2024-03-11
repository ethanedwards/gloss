from llm.llm import llm
import config
import asyncio
from anthropic import AsyncAnthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
) 

class claude(llm):
    def __init__(self):
        super().__init__('claude')

        self.aclient = AsyncAnthropic(
            api_key=config.anthropic_api_key,
        )

        self.requestcount = 0
        self.requestmax = 4


        
    @retry(wait=wait_random_exponential(min=5, max=60), stop=stop_after_attempt(6))
    async def get_completion_async(self, messages:dict, model:str="claude-3-opus-20240229", max_tokens:int=1024, temperature:float=0.8):
        while(self.requestcount >= self.requestmax):
            await asyncio.sleep(60)
        self.requestcount += 1
        message = await self.create_api_message(self.aclient, messages, model, max_tokens, temperature)
        # Use the event loop associated with the TokenBucket
        self.requestcount -= 1
        return message.content[0].text
    

    def get_completion_sync(self, messages:dict, model:str="claude-3-opus-20240229", max_tokens:int=1024, temperature:float=0.8):
        raise NotImplementedError("This method should be implemented by subclass.")
    
    def format_messages(self, userprompt:str, systemprompt:str='You are a helpful assistant'):
        #Put system prompt first, used in later function to remove it
        return [
            systemprompt,
            {"role": "user", "content": userprompt}
        ]
    
    def create_api_message(self, cli, messages:dict, model:str="claude-3-opus-20240229", max_tokens:int=1024, temperature:float=0.8):
        #Remove the system prompt
        system = messages[0]
        messages = messages[1:]
        message = cli.messages.create(
            system=system,
            max_tokens=max_tokens,
            messages=messages,
            model=model,
            temperature=temperature,
        )
        return message
    
        
