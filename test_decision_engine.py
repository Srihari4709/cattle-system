import sqlite3
from decision_engine import run_decision_engine

def run_tests():
    print("==================================================")
    print("Testing Smart Kangeyam Cattle Decision Engine")
    print("==================================================")
    
    # 1. Test Case A: Lakshmi (High milk production, high costs)
    res_a = run_decision_engine("KANG-001")
    print(f"\n[Case A] {res_a['name']}")
    print(f"  Health Score: {res_a['health_score']}, Productivity Score: {res_a['productivity_score']}")
    print(f"  Economic Score: {res_a['economic_score']}, Breeding Score: {res_a['breeding_score']}")
    print(f"  Overall Score: {res_a['overall_score']}, Confidence: {res_a['confidence_level']}%")
    print(f"  Recommendation: {res_a['recommendation']}")
    print(f"  Alerts: {res_a['global_alerts']}")
    print(f"  Explanations: {res_a['explanation']}")
    assert res_a['recommendation'] in ["Consider Sale", "Monitor Closely"], "Case A failed recommendation check"
    assert res_a['economic_score'] <= 40, "Case A economic score should be low due to high costs"

    # 2. Test Case B: Gauri (Vaccination Overdue)
    res_b = run_decision_engine("KANG-002")
    print(f"\n[Case B] {res_b['name']}")
    print(f"  Health Score: {res_b['health_score']}, Overall Score: {res_b['overall_score']}")
    print(f"  Recommendation: {res_b['recommendation']}")
    print(f"  Alerts: {res_b['global_alerts']}")
    assert "Vaccination Overdue Alert" in res_b['global_alerts'], "Case B vaccine overdue alert missing"
    assert res_b['recommendation'] == "Monitor Closely", "Case B recommendation should be Monitor Closely"

    # 3. Test Case C: Sita (Declining production)
    res_c = run_decision_engine("KANG-003")
    print(f"\n[Case C] {res_c['name']}")
    print(f"  Productivity Score: {res_c['productivity_score']}, Overall Score: {res_c['overall_score']}")
    print(f"  Recommendation: {res_c['recommendation']}")
    print(f"  Alerts: {res_c['global_alerts']}")
    assert any("declining" in p.lower() for p in res_c['productivity_penalties']), "Case C should have declining production penalty"
    assert "Declining Milk Yield Alert" in res_c['global_alerts'], "Case C declining milk alert missing"

    # 4. Test Case D: Rathi (Missing Health Records)
    res_d = run_decision_engine("KANG-004")
    print(f"\n[Case D] {res_d['name']}")
    print(f"  Health Score: {res_d['health_score']}, Confidence Level: {res_d['confidence_level']}%")
    print(f"  Recommendation: {res_d['recommendation']}")
    print(f"  Alerts: {res_d['global_alerts']}")
    assert "Missing Health History Alert" in res_d['global_alerts'], "Case D missing health history alert missing"
    assert res_d['confidence_level'] < 90, "Case D confidence level should be reduced due to missing health history"

    # 5. Test Case E: Karpagam (Young Heifer)
    res_e = run_decision_engine("KANG-005")
    print(f"\n[Case E] {res_e['name']}")
    print(f"  Productivity Score: {res_e['productivity_score']}, Breeding Score: {res_e['breeding_score']}")
    print(f"  Overall Score: {res_e['overall_score']}")
    print(f"  Recommendation: {res_e['recommendation']}")
    assert res_e['recommendation'] in ["Breeding Candidate", "Continue Dairy Production"], "Case E young heifer recommendation wrong"
    assert res_e['breeding_score'] >= 75, "Case E young heifer breeding score should be high"

    # 6. Test Case F: Sona (Sudden Drop)
    res_f = run_decision_engine("KANG-006")
    print(f"\n[Case F] {res_f['name']}")
    print(f"  Productivity Score: {res_f['productivity_score']}, Overall Score: {res_f['overall_score']}")
    print(f"  Recommendation: {res_f['recommendation']}")
    print(f"  Alerts: {res_f['global_alerts']}")
    assert "Sudden Milk Drop Alert" in res_f['global_alerts'], "Case F sudden drop alert missing"
    assert res_f['recommendation'] == "Monitor Closely", "Case F recommendation should be Monitor Closely"

    # 7. Test Case G: Meena (Fluctuating Market Value)
    res_g = run_decision_engine("KANG-007")
    print(f"\n[Case G] {res_g['name']}")
    print(f"  Market Value: Rs. {res_g['market_value']}")
    print(f"  Overall Score: {res_g['overall_score']}")
    print(f"  Recommendation: {res_g['recommendation']}")
    
    print("\n==================================================")
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
