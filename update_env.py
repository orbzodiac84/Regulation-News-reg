import os

env_path = ".env"
new_key = "AIzaSyAf9TWgmVuaDftPOb2iec3QhI41HdNWZV0"

with open(env_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

with open(env_path, "w", encoding="utf-8") as f:
    for line in lines:
        if line.startswith("GEMINI_API_KEY="):
            f.write(f"GEMINI_API_KEY={new_key}\n")
        else:
            f.write(line)

print("Updated .env successfully.")
