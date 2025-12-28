
import os

env_path = os.path.join(os.getcwd(), '.env')
v2_config = """
# v2.0 Environment Variables
NEXT_PUBLIC_SUPABASE_URL_V2=https://latgtrpmymqdlysgolat.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY_V2=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhdGd0cnBteW1xZGx5c2dvbGF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY5MTM0NzAsImV4cCI6MjA4MjQ4OTQ3MH0.qZHjqbon4e90aH_xcfjYAiNhJFAAYqla4787TakKkzo
"""

with open(env_path, 'a', encoding='utf-8') as f:
    f.write(v2_config)

print("v2.0 environment variables appended to .env")
