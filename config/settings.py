# Model Configuration for 2-Tier Hybrid Analysis

# Tier 1: Gatekeeper (Fast, cheap filtering)
MODEL_FILTER_ID = "gemini-2.5-flash-lite"

# Tier 2: Analyst (Deep analysis for important news)
MODEL_ANALYZER_ID = "gemini-3-flash-preview"

# Fallback if Tier 2 model unavailable
MODEL_ANALYZER_FALLBACK = "gemini-1.5-pro"

# Importance threshold to trigger Tier 2 analysis
# Only articles with importance_score >= this value get deep analysis
IMPORTANCE_THRESHOLD = 4

# Rate limiting (seconds between API calls)
# With billing enabled, 0.5s is safe and fast
API_CALL_DELAY = 0.5
