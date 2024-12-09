#Handle API and org keys
from dotenv import load_dotenv
import os

load_dotenv()

#API keys and private information
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')

class Config:
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    # Add other configuration variables