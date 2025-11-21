from .llm import llm
#import config.py
import config as config
import asyncio
import os
from typing import Optional
from anthropic import AsyncAnthropic, Anthropic
import anthropic as anthropic_module
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

class claude(llm):
    def __init__(self):
        super().__init__('claude')
        self.requestcount = 0
        self.requestmax = 10
        self.request_timeout_seconds = int(os.getenv("GLOSS_API_TIMEOUT", "600"))

        self.aclient = AsyncAnthropic(
            api_key=config.anthropic_api_key,
            timeout=self.request_timeout_seconds,
            max_retries=0,
        )
        self.client = Anthropic(
            api_key=config.anthropic_api_key,
            timeout=self.request_timeout_seconds,
            max_retries=0,
        )


    def _rebuild_clients(self) -> None:
        self.aclient = AsyncAnthropic(
            api_key=config.anthropic_api_key,
            timeout=self.request_timeout_seconds,
            max_retries=0,
        )
        self.client = Anthropic(
            api_key=config.anthropic_api_key,
            timeout=self.request_timeout_seconds,
            max_retries=0,
        )

    async def get_completion_async(self, messages:dict, model:str="claude-sonnet-4-5-20250929", max_tokens:int=1024, temperature:float=0.8, timeout_seconds: Optional[int]=None):
        while self.requestcount >= self.requestmax:
            await asyncio.sleep(0.1)
        self.requestcount += 1
        try:
            effective_timeout = timeout_seconds if timeout_seconds is not None else self.request_timeout_seconds
            try:
                message = await asyncio.wait_for(
                    self.create_api_message(self.aclient, messages, model, max_tokens, temperature),
                    timeout=effective_timeout,
                )
            except Exception as e:
                # Handle transient connection errors broadly (SDK class name or message text)
                if e.__class__.__name__ == "APIConnectionError" or "Connection error" in str(e):
                    logger.warning("Transient connection error detected. Rebuilding clients and retrying once.")
                    self._rebuild_clients()
                    message = await asyncio.wait_for(
                        self.create_api_message(self.aclient, messages, model, max_tokens, temperature),
                        timeout=effective_timeout,
                    )
                else:
                    raise
            return message.content[0].text
        except Exception as e:
            logger.warning(f"LLM request failed: {type(e).__name__}: {e!s}")
            raise
        finally:
            self.requestcount -= 1
    
    def get_completion_sync(self, messages:dict, model:str="claude-sonnet-4-5-20250929", max_tokens:int=1024, temperature:float=0.8):
        message = self.create_api_message(self.client, messages, model, max_tokens, temperature)
        return message.content[0].text
    
    async def get_completion_stream_async(self, messages:dict, model:str="claude-sonnet-4-5-20250929", max_tokens:int=1024, temperature:float=0.8, method=print):
        system = messages[0]
        messages = messages[1:]
        stream = await self.aclient.messages.create(
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            model=model,
            stream=True,
        )
        async for event in stream:
            method(event)

    def get_completion_stream_sync(self, messages:dict, model:str="claude-sonnet-4-5-20250929", max_tokens:int=1024, temperature:float=0.8, method=print):
        system = messages[0]
        messages = messages[1:]
        print(f"Messages: {messages}")
        print(f"System: {system}")
        stream = self.client.messages.create(
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            model=model,
            stream=True,
        )
        for event in stream:
            yield event
    
    def format_messages(self, userprompt:str, systemprompt:str='You are a helpful assistant'):
        #Put system prompt first, used in later function to remove it
        return [
            systemprompt,
            {"role": "user", "content": userprompt}
        ]
    
    def format_messages_buffer(self, buffer:list, systemprompt:str='You are a helpful assistant'):
        messages = [
            systemprompt
        ]
        for item in buffer:
            messages.append({"role": item["role"], "content": item["content"]})
        return messages
    
    def create_api_message(self, cli, messages:dict, model:str="claude-sonnet-4-5-20250929", max_tokens:int=1024, temperature:float=0.8):
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
    
        
