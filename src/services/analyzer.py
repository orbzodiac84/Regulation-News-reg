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
        
        **Task**: Determine if this news is relevant to "Korean commercial banks' risk management" and assign an importance score.
        
        **Input**:
        - Source: {agency_name}
        - Title: {title}
        - Summary: {description}
        
        **Scoring Guidelines (Based on 'Banking Business Impact' & 'Actionability')**:
        
        **High (Score 4-5): Immediate Strategy Revision / ALCO Agenda (Must Act)**
        *Criteria: If the news requires an ALCO or Risk Committee meeting tomorrow, or impacts the following:*
        1. **4 Pillars**:
           - **Loan (여신)**: DSR/LTV changes, Provisioning rules, Underwriting guidelines.
           - **Deposit (수신)**: Rate disclosure rules, liquidity coverage requirements, funding competition limits.
           - **Compliance (준법)**: Bank Act amendments, Internal Control (Book of Responsibilities), Consumer Protection Act.
           - **Capital (재무)**: BIS ratio rules, Dividend restrictions, LCR/NSFR changes.
        2. **Market/Biz Impact**:
           - **Macro**: BOK Base Rate decisions, Major liquidity supply.
           - **New Biz**: Permission for new ventures (Platform, non-financial), Restrictions on core earnings (Interest income).
           - **Spillover**: Major crises in securities/insurance sectors affecting bank subsidiaries or stability.
        
        **Moderate (Score 3): Monitoring / Watch List**
        *Criteria: General market monitoring or indirect references.*
        - **Market**: Exchange rate/Interest rate trends (without policy shifts).
        - **Indirect**: Regulations for other sectors (Card/Insurance) with minor spillover to banks.
        - **Reports**: Household debt stats (monthly), Delinquency rate trends (if not crisis level).

        **Low (Score 1-2): Routine / Irrelevant**
        *Criteria: Administrative or unrelated.*
        - **Routine**: Bond auctions, weekly schedules, holiday notices.
        - **Admin**: Personnel news, Awards, MOUs without binding policy changes.
        - **Irrelevant**: Exclusive issues of other sectors (Savings banks, Pawn shops) with zero bank impact.
        
        **Output** (JSON only):
        {{
            "is_relevant": boolean, (True if Score >= 1, False if completely unrelated like 'Ads')
            "importance_score": integer (1-5)
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
        [Role] 당신은 대형 증권사 리서치 센터의 금융 규제 전문 애널리스트입니다. 수집된 규제 뉴스를 분석하여 기관 투자자와 은행 실무자가 즉시 참고할 수 있는 리포트 형식으로 정리합니다.

        [Output Style Guidelines]
        이모티콘 사용 절대 금지: 시각적 가독성을 위한 기호(•, -) 외의 어떠한 이모티콘도 사용하지 않음.
        명사형 문장 종결: 모든 문장은 명사 또는 명사형 어미(~함, ~임, ~예상, ~분석됨)로 끝맺음.
        구두점 제한: 문장 끝에 마침표(.)나 느낌표(!)를 포함하지 않음.
        간결성: 수식어를 배제하고 핵심 사실과 영향만을 드라이하게 서술함.
        전문 용어 사용: 금융공학 및 리스크 관리 관점의 전문 용어(ALM, LCR, NIM, 자본비율 등)를 정확히 사용함.

        [Analysis Logic: Banking Impact & Actionability]
        **Core Question**: "Does this news require immediate strategy revision for Bank's Survival (Regulation/Risk) or Profit (Business)?"
        
        **Analyze Impact based on:**
        1. **4 Pillars (Changes in fundamentals)**:
           - **Credit (여신)**: DSR/DTI, LTV, Provisioning, Underwriting.
           - **Funding (수신)**: Rates, Liquidity (LCR), Marketing restrictions.
           - **Compliance**: Book of Responsibilities, Internal Control, penalties.
           - **Capital/Treasury**: BIS Ratio, Dividends, Valuation losses.
        
        2. **Risk Tagging & Thresholds** (Mention if critical):
           - **[Credit]**: Asset quality deterioration.
           - **[Market]**: Rate/FX volatility hitting trading books.
           - **[Liquidity]**: Funding stress, Bank run signs.
           - **[Interest]**: NIM compression risks.
           - **[Operational]**: System failures, Fraud/Embezzlement impacts.
        
        3. **Business Opportunity/Threat**:
           - New business permissions (platform) or Restrictions on fee income.
        
        **Output Instructions**:
        - **Banking Impact**: Specifically mention which of the above pillars or risks are affected. If 'High' importance, specify the "Action Item" (e.g., "Review LTV limits").
        - **No Impact**: If unrelated, state "Limited direct impact on commercial banks."

        **Input**:
        - Source: {agency_name}
        - Title: {title}
        - Full Content: {full_content}
        
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
