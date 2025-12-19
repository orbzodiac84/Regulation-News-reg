from src.services.analyzer import RegulationAnalyzer

def test_analysis():
    analyzer = RegulationAnalyzer()
    
    # Dummy data (Financial Services Commission press release style)
    title = "[보도자료] 은행권 가계대출 관리방안 마련"
    agency = "금융위원회"
    content = """
    금융위원회는 오늘(19일) 은행권 가계대출 증가세를 억제하기 위한 새로운 관리방안을 발표했습니다.
    이번 방안에 따라 은행들은 자율적으로 설정한 연간 가계대출 증가 목표치를 엄격히 준수해야 합니다.
    이를 초과할 경우 내년도 대출 한도 설정에 불이익을 받게 됩니다.
    또한, DSR(총부채원리금상환비율) 산정 시 미래 금리 변동 위험을 반영하는 '스트레스 DSR' 제도가 도입됩니다.
    이는 변동금리 대출 이용 차주의 대출 한도를 축소시키는 효과가 있습니다.
    금융당국은 이번 조치를 통해 가계부채 증가율을 경상성장률 범위 내에서 안정적으로 관리한다는 계획입니다.
    """
    
    print(f"Analyzing Item: {title}")
    result = analyzer.analyze(title, content, agency)
    
    if result:
        print("\n[Analysis Result]")
        print(f"Risk Level: {result.get('risk_level')}")
        print("Summary:")
        for line in result.get('summary', []):
            print(f"- {line}")
        print(f"\nImpact: {result.get('impact_analysis')}")
        print(f"Keywords: {result.get('keywords')}")
    else:
        print("Analysis failed.")

if __name__ == "__main__":
    try:
        test_analysis()
    except Exception:
        import traceback
        traceback.print_exc()
