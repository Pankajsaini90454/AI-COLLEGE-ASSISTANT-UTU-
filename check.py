import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load your Gemini API key
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"), transport="rest")

print("Searching for your available embedding models...")
for m in genai.list_models():
    if 'embedContent' in m.supported_generation_methods:
        print(f"[FOUND] {m.name}")