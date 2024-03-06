import os
import asyncio
import config
from anthropic import AsyncAnthropic

client = AsyncAnthropic(
    # This is the default and can be omitted
    api_key=config.anthropic_api_key,
)


async def anthropicPrompt(messages:dict, model:str="claude-3-opus-20240229", max_tokens:int=1024, temperature:float=0.8):
    message = await client.messages.create(
        max_tokens=max_tokens,
        messages=messages,
        model=model,
    )
    return message.content