import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

print("Listing models with new SDK:")
try:
    for model in client.models.list():
        if "flash" in model.name.lower():
             print(f"- {model.name}")
except Exception as e:
    print(f"Error listing models: {e}")

print("\nTesting gemini-2.0-flash generation:")
try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Hello"
    )
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"gemini-2.0-flash failed: {e}")

print("\nTesting gemini-1.5-flash generation:")
try:
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Hello"
    )
    print(f"Success! Response: {response.text}")
except Exception as e:
    print(f"gemini-1.5-flash failed: {e}")
