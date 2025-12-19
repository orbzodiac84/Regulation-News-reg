import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("GEMINI_API_KEY")

models = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-lite-preview-02-05"
]

print("Testing Raw HTTP API...")

for m in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}]
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        print(f"\n--- {m} ---")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS!")
        else:
            print(f"Error: {response.text[:200]}") # Print first 200 chars of error
            
    except Exception as e:
        print(f"Request failed: {e}")
