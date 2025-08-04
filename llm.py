import asyncio
import os
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI
load_dotenv('.env', override = True)

class Open_AI:
    def __init__(self):
        api_key = os.environ.get('OPENAI_API_KEY')
        self.client = OpenAI(api_key = api_key)
        self.async_client = AsyncOpenAI(api_key = api_key)

    def responses(self, model: str, messages: list[dict]):
        response = self.client.responses.create(
            model = model,
            input = messages,
            reasoning = {
                'effort': 'high', 
                'summary': 'auto'
            } if model.startswith('o') else None,
        )
        return response.output_text
    
    async def async_responses(self, model: str, messages: list[dict]):
        response = await self.async_client.responses.create(
            model = model,
            input = messages,
            reasoning = {
                'effort': 'high', 
                'summary': 'auto'
            } if model.startswith('o') else None,
        )
        return response.output_text
    
    def responses_structured_output(self, model: str, messages: list[dict], structure):
        response = self.client.responses.parse(
            model = model,
            input = messages,
            reasoning = {
                'effort': 'high', 
                'summary': 'auto'
            } if model.startswith('o') else None,
            text_format = structure
        )
        return response.output_parsed

    async def async_responses_structured_output(self, model: str, messages: list[dict], structure):
        response = await self.async_client.responses.parse(
            model = model,
            input = messages,
            reasoning = {
                'effort': 'high', 
                'summary': 'auto'
            } if model.startswith('o') else None,
            text_format = structure
        )
        return response.output_parsed

async def main():
    open_ai = Open_AI()
    response = await open_ai.async_responses('gpt-4o-mini', [
        {'role': 'user', 'content': 'What is the capital of France?'}
    ])
    print(response)

if __name__ == '__main__':
    asyncio.run(main())
