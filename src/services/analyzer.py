"""
2-Tier Hybrid Analyzer for MarketPulse-Reg

Tier 1 (Gatekeeper): Fast filtering with gemini-2.5-flash-lite
Tier 2 (Analyst): Deep analysis with gemini-3-flash-preview for important news only
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

# Import settings
from config.settings import (
    MODEL_FILTER_ID, 
    MODEL_ANALYZER_ID, 
    MODEL_ANALYZER_FALLBACK,
    IMPORTANCE_THRESHOLD,
    API_CALL_DELAY
)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class HybridAnalyzer:
    """2-Tier Hybrid Analyzer with Gatekeeper + Analyst pipeline."""
    
    def __init__(self):
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in .env")
        
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.filter_model = MODEL_FILTER_ID
        self.analyzer_model = MODEL_ANALYZER_ID
        self.analyzer_fallback = MODEL_ANALYZER_FALLBACK
        self.importance_threshold = IMPORTANCE_THRESHOLD
        
    def _call_api(self, model: str, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Call Gemini API with retry logic."""
        base_delay = 10
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                if response.text:
                    return response.text
                return None
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    delay = base_delay * (attempt + 1)
                    logger.warning(f"Rate Limit hit. Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(delay)
                elif "404" in error_str or "NOT_FOUND" in error_str:
                    logger.error(f"Model {model} not found")
                    return None
                else:
                    logger.error(f"API Error: {error_str[:200]}")
                    return None
        
        logger.error("Failed after max retries")
        return None

    def filter(self, title: str, description: str, agency_name: str) -> Optional[Dict[str, Any]]:
        """
        Tier 1: Gatekeeper - Quick relevance filtering.
        Uses only title + description to save tokens.
        """
        prompt = f"""
        You are a news relevance filter for a Korean commercial bank's risk management team.
        
        **Task**: Determine if this news is relevant to "Korean commercial banks' risk management, regulatory compliance, or macroeconomic indicators".
        
        **Input**:
        - Source: {agency_name}
        - Title: {title}
        - Summary: {description}
        
        **Criteria**:
        - Relevant: Banking regulations, monetary policy, interest rates, debt, capital requirements, compliance rules
        - Not Relevant: Promotions, events, awards, internal appointments, unrelated industries
        
        **Output** (JSON only):
        {{
            "is_relevant": boolean,
            "importance_score": integer (1-5, where 5 is most important)
        }}
        """
        
        response_text = self._call_api(self.filter_model, prompt)
        
        if response_text:
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse filter response: {response_text[:100]}")
                return None
        return None

    def analyze(self, title: str, full_content: str, agency_name: str) -> Optional[Dict[str, Any]]:
        """
        Tier 2: Analyst - Deep analysis for important news.
        Uses full article content.
        """
        prompt = f"""
        You are a **Senior Risk Analyst** at a major Korean commercial bank.
        
        **Task**: Provide a detailed analysis of this regulatory news for the risk management team.
        
        **Input**:
        - Source: {agency_name}
        - Title: {title}
        - Full Content: {full_content}
        
        **Requirements**:
        1. **Summary**: 3 concise bullet points with emojis (Korean, "Jjirasi" style)
        2. **Impact Analysis**: How this affects Korean commercial banks specifically
        3. **Risk Level**: High / Medium / Low
        4. **Recommended Actions**: What the bank should do in response
        5. **Keywords**: 3-5 relevant keywords
        
        **Output** (JSON only):
        {{
            "summary": ["string", "string", "string"],
            "impact_analysis": "string",
            "risk_level": "High" | "Medium" | "Low",
            "recommended_actions": "string",
            "keywords": ["string", ...]
        }}
        """
        
        # Try primary model
        response_text = self._call_api(self.analyzer_model, prompt)
        
        # Fallback if primary fails
        if not response_text:
            logger.warning(f"Primary model {self.analyzer_model} failed. Trying fallback {self.analyzer_fallback}")
            response_text = self._call_api(self.analyzer_fallback, prompt)
        
        if response_text:
            try:
                result = json.loads(response_text)
                result['analyzed_by'] = self.analyzer_model
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse analysis response: {response_text[:100]}")
                return None
        return None

    def process(self, article: Dict[str, Any], agency_name: str) -> Dict[str, Any]:
        """
        Main pipeline: Filter -> Analyze (if important)
        
        Returns combined result with filter and analysis data.
        """
        title = article.get('title', '')
        description = article.get('description') or article.get('content', '')[:200] or title
        full_content = article.get('content') or title
        
        # Step 1: Gatekeeper
        filter_result = self.filter(title, description, agency_name)
        time.sleep(API_CALL_DELAY)  # Rate limit protection
        
        if not filter_result:
            logger.warning(f"Filter failed for: {title[:50]}")
            return {
                "is_relevant": False,
                "importance_score": 0,
                "filter_status": "ERROR",
                "analysis_status": "SKIPPED"
            }
        
        is_relevant = filter_result.get('is_relevant', False)
        importance_score = filter_result.get('importance_score', 0)
        
        # Build result
        result = {
            "is_relevant": is_relevant,
            "importance_score": importance_score,
            "filter_status": "OK"
        }
        
        # Step 2: Analyst (only for important news)
        if is_relevant and importance_score >= self.importance_threshold:
            logger.info(f"Proceeding to Tier 2 analysis (Score: {importance_score}): {title[:40]}...")
            
            analysis = self.analyze(title, full_content, agency_name)
            time.sleep(API_CALL_DELAY)  # Rate limit protection
            
            if analysis:
                result.update(analysis)
                result["analysis_status"] = "ANALYZED"
                logger.info(f"Analyzed successfully (Model: {self.analyzer_model}): {title[:40]}")
            else:
                result["analysis_status"] = "ANALYSIS_FAILED"
                logger.warning(f"Analysis failed: {title[:40]}")
        else:
            result["analysis_status"] = "SKIPPED"
            logger.info(f"Filtered out (Score: {importance_score}, Relevant: {is_relevant}): {title[:40]}")
        
        return result


# Backward compatibility alias
RegulationAnalyzer = HybridAnalyzer


if __name__ == "__main__":
    analyzer = HybridAnalyzer()
    logger.info("HybridAnalyzer initialized successfully.")
