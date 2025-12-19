import os
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

candidates = [
    "gemini-2.5-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite-preview-02-05",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro"
]

print("Starting sequential test with new SDK...")

for model_name in candidates:
    print(f"\n--- Testing {model_name} ---")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Hello",
            config=None
        )
        print(f"SUCCESS! {model_name} worked.")
        print(f"Response: {response.text}")
        # Dont break, list all working ones
    except Exception as e:
         # Simplify error message
        err = str(e)
        if "429" in err:
            print(f"FAILED {model_name}: Rate Limit (429)")
        elif "404" in err:
            print(f"FAILED {model_name}: Not Found (404)")
        else:
            print(f"FAILED {model_name}: {err[:100]}...")
    
    time.sleep(2)
