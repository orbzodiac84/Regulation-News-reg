
import os

def setup_frontend_env():
    # Path to web/.env.local
    web_env_path = os.path.join(os.getcwd(), 'web', '.env.local')
    
    # Check if exists
    if not os.path.exists(web_env_path):
        print(f"Warning: {web_env_path} does not exist. Creating new one.")
        
    # v2.0 Configuration (Same as root .env, plus the TOGGLE flag)
    v2_frontend_config = """
# v2.0 Development Configuration
NEXT_PUBLIC_USE_V2_DB=true
NEXT_PUBLIC_SUPABASE_URL_V2=https://latgtrpmymqdlysgolat.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY_V2=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhdGd0cnBteW1xZGx5c2dvbGF0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY5MTM0NzAsImV4cCI6MjA4MjQ4OTQ3MH0.qZHjqbon4e90aH_xcfjYAiNhJFAAYqla4787TakKkzo
"""

    try:
        with open(web_env_path, 'a', encoding='utf-8') as f:
            f.write(v2_frontend_config)
        print(f"Success: Updated {web_env_path} with v2.0 settings.")
    except Exception as e:
        print(f"Error updating web/.env.local: {e}")

if __name__ == "__main__":
    setup_frontend_env()
