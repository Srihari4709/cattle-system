import sqlite3
from datetime import datetime, timedelta
from database import get_db_connection

def calculate_health_score(cattle_id, cursor):
    # Base health score is 100
    score = 100.0
    penalties = []
    explanations = []
    
    # 1. Check Vaccination Status
    cursor.execute("""
        SELECT record_date, details FROM health_records 
        WHERE cattle_id = ? AND record_type = 'vaccination'
        ORDER BY record_date DESC LIMIT 1
    """, (cattle_id,))
    latest_vaccine = cursor.fetchone()
    
    # Get cattle age to avoid penalizing very young calves
    cursor.execute("SELECT age FROM cattle WHERE id = ?", (cattle_id,))
    cattle_age = cursor.fetchone()['age']
    
    if latest_vaccine:
        vaccine_date = datetime.strptime(latest_vaccine['record_date'], "%Y-%m-%d")
        days_since_vaccine = (datetime.now() - vaccine_date).days
        if days_since_vaccine > 365:
            score -= 30
            penalties.append("Vaccination Overdue (> 365 days)")
        elif days_since_vaccine > 180:
            score -= 15
            penalties.append("Vaccination Overdue (> 180 days)")
        else:
            explanations.append("Vaccination up to date")
    else:
        # If age is > 0.5 years and has no vaccination records
        if cattle_age > 0.5:
            score -= 35
            penalties.append("Missing Vaccination History")
        else:
            explanations.append("Calf - vaccination schedule pending")

    # 2. Check Illness History and Recency of Illness (last 30 days)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT record_date, details, cost FROM health_records
        WHERE cattle_id = ? AND record_type = 'medical_treatment' AND record_date >= ?
        ORDER BY record_date DESC
    """, (cattle_id, thirty_days_ago))
    recent_illnesses = cursor.fetchall()
    
    if recent_illnesses:
        illness_count = len(recent_illnesses)
        illness_penalty = min(illness_count * 15, 40)
        score -= illness_penalty
        penalties.append(f"Recent Illnesses ({illness_count} event(s))")
        
        # Check recency (within last 7 days)
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        most_recent_date = recent_illnesses[0]['record_date']
        if most_recent_date >= seven_days_ago:
            score -= 15
            penalties.append("Illness in the last 7 days")
    else:
        explanations.append("No illnesses in the last 30 days")
        
    # 3. Medical Expenses
    total_med_cost = sum(record['cost'] for record in recent_illnesses) if recent_illnesses else 0.0
    if total_med_cost > 250:
        score -= 20
        penalties.append(f"Extremely High Medical Cost (Rs. {total_med_cost:.2f})")
    elif total_med_cost > 100:
        score -= 10
        penalties.append(f"High Medical Cost (Rs. {total_med_cost:.2f})")
        
    score = max(0.0, min(100.0, score))
    return round(score), penalties, explanations

def calculate_productivity_score(cattle_id, cursor):
    # Base productivity score calculation
    score = 100.0
    penalties = []
    explanations = []
    
    # Get cattle profile
    cursor.execute("SELECT age FROM cattle WHERE id = ?", (cattle_id,))
    cattle_age = cursor.fetchone()['age']
    
    # 1. Fetch 30 days production records
    cursor.execute("""
        SELECT record_date, milk_production FROM production_records
        WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 30
    """, (cattle_id,))
    records = cursor.fetchall()
    
    if not records:
        if cattle_age < 2.0:
            score = 75.0
            explanations.append("Young heifer, not yet lactating (Expected status)")
        else:
            score = 20.0
            penalties.append("No production records for mature cow")
        return round(score), penalties, explanations
        
    # 2. Avg Daily Milk Yield
    total_milk = sum(r['milk_production'] for r in records)
    avg_milk = total_milk / len(records)
    
    if avg_milk >= 12.0:
        base_yield_score = 95.0
        explanations.append(f"Excellent milk production (Avg: {avg_milk:.1f} L/day)")
    elif avg_milk >= 8.0:
        base_yield_score = 80.0
        explanations.append(f"Good milk production (Avg: {avg_milk:.1f} L/day)")
    elif avg_milk >= 4.0:
        base_yield_score = 60.0
        explanations.append(f"Moderate milk production (Avg: {avg_milk:.1f} L/day)")
    elif avg_milk > 0:
        base_yield_score = 40.0
        penalties.append(f"Low milk production (Avg: {avg_milk:.1f} L/day)")
    else:
        # avg_milk == 0
        if cattle_age < 2.0:
            base_yield_score = 75.0
            explanations.append("Young Heifer (No milk production expected)")
        else:
            base_yield_score = 15.0
            penalties.append("Mature cow with zero milk yield")
            
    score = base_yield_score
    
    # Skip trend / sudden drop checks for non-lactating young animals
    if avg_milk == 0 and cattle_age < 2.0:
        return round(score), penalties, explanations
        
    # 3. Productivity Trend (Last 7 days vs previous 23 days)
    if len(records) >= 10:
        recent_records = records[:7]
        older_records = records[7:]
        
        avg_recent = sum(r['milk_production'] for r in recent_records) / len(recent_records)
        avg_older = sum(r['milk_production'] for r in older_records) / len(older_records) if older_records else avg_recent
        
        if avg_older > 0:
            ratio = avg_recent / avg_older
            if ratio < 0.65:
                score -= 25
                penalties.append("Severely declining milk production")
            elif ratio < 0.85:
                score -= 15
                penalties.append("Declining milk production")
            elif ratio >= 1.05:
                explanations.append("Increasing milk production trend")
                
    # 4. Sudden Drop Detection (latest 2 days vs previous 5 days)
    if len(records) >= 7:
        latest_2 = records[:2]
        prev_5 = records[2:7]
        
        avg_latest = sum(r['milk_production'] for r in latest_2) / 2
        avg_prev = sum(r['milk_production'] for r in prev_5) / 5
        
        if avg_prev > 2.0: # Only check sudden drops if baseline is reasonable
            drop_ratio = avg_latest / avg_prev
            if drop_ratio < 0.50:
                score -= 30
                penalties.append("Sudden drop in productivity detected")
                
    score = max(0.0, min(100.0, score))
    return round(score), penalties, explanations

def calculate_economic_score(cattle_id, cursor):
    # Milk Price = Rs. 40.0 per Liter (Kangeyam milk is premium, usually fetches good price)
    # Feed Cost = Rs. 30.0 per kg
    MILK_PRICE = 40.0
    FEED_COST = 30.0
    
    score = 100.0
    penalties = []
    explanations = []
    
    # Get age
    cursor.execute("SELECT age FROM cattle WHERE id = ?", (cattle_id,))
    cattle_age = cursor.fetchone()['age']
    
    # 1. Fetch 30 days production & finance logs
    cursor.execute("""
        SELECT milk_production, feed_consumption FROM production_records
        WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 30
    """, (cattle_id,))
    prod_records = cursor.fetchall()
    
    cursor.execute("""
        SELECT maintenance_cost, estimated_market_value FROM financial_records
        WHERE cattle_id = ? ORDER BY record_date DESC LIMIT 30
    """, (cattle_id,))
    fin_records = cursor.fetchall()
    
    # Calculate Medical cost last 30 days
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT SUM(cost) as total_med FROM health_records
        WHERE cattle_id = ? AND record_date >= ?
    """, (cattle_id, thirty_days_ago))
    med_res = cursor.fetchone()
    total_medical_expenses = med_res['total_med'] if med_res['total_med'] is not None else 0.0
    daily_medical_cost = total_medical_expenses / 30.0
    
    # Handle new or empty records
    if not prod_records or not fin_records:
        if cattle_age < 2.0:
            score = 65.0
            explanations.append("Young animal - investment phase (No immediate returns)")
        else:
            score = 30.0
            penalties.append("Insufficient financial and yield records")
        return round(score), penalties, explanations
        
    avg_milk = sum(r['milk_production'] for r in prod_records) / len(prod_records)
    avg_feed = sum(r['feed_consumption'] for r in prod_records) / len(prod_records)
    avg_maint = sum(r['maintenance_cost'] for r in fin_records) / len(fin_records)
    
    daily_revenue = avg_milk * MILK_PRICE
    daily_feed_expense = avg_feed * FEED_COST
    daily_total_expense = daily_feed_expense + avg_maint + daily_medical_cost
    
    # Check if young animal
    if avg_milk == 0 and cattle_age < 2.0:
        score = 70.0
        explanations.append(f"Heifer maintenance costs: Rs. {daily_total_expense:.2f}/day (Appropriate)")
        return round(score), penalties, explanations
        
    # Standard Economic return / efficiency
    if daily_total_expense > 0:
        efficiency_ratio = daily_revenue / daily_total_expense
    else:
        efficiency_ratio = 1.0
        
    if efficiency_ratio >= 1.8:
        score = 95.0
        explanations.append(f"Highly profitable (Revenue: Rs. {daily_revenue:.1f}/day, Costs: Rs. {daily_total_expense:.1f}/day)")
    elif efficiency_ratio >= 1.3:
        score = 80.0
        explanations.append(f"Profitable return (Efficiency ratio: {efficiency_ratio:.2f}x)")
    elif efficiency_ratio >= 1.0:
        score = 60.0
        explanations.append("Breaking even (Revenue matches expenses)")
    elif efficiency_ratio >= 0.7:
        score = 40.0
        penalties.append(f"Low profit margin (Revenue: Rs. {daily_revenue:.1f}/day, Costs: Rs. {daily_total_expense:.1f}/day)")
    else:
        score = 20.0
        penalties.append(f"Uneconomical: Daily expenses (Rs. {daily_total_expense:.1f}) exceed revenue (Rs. {daily_revenue:.1f})")
        
    # High medical/maintenance cost warning relative to production
    if daily_medical_cost > 5.0:
        score -= 10
        penalties.append("High daily veterinary expense amortization")
        
    if avg_maint > 10.0:
        score -= 10
        penalties.append("High daily housing/labor maintenance overhead")
        
    score = max(0.0, min(100.0, score))
    return round(score), penalties, explanations

def calculate_breeding_score(cattle_id, cursor):
    score = 50.0
    penalties = []
    explanations = []
    
    # Get cattle profile
    cursor.execute("SELECT age FROM cattle WHERE id = ?", (cattle_id,))
    cattle_age = cursor.fetchone()['age']
    
    # Check breeding records
    cursor.execute("""
        SELECT record_date, event_type, details, calving_interval_days FROM breeding_records
        WHERE cattle_id = ? ORDER BY record_date DESC
    """, (cattle_id,))
    breeding_history = cursor.fetchall()
    
    # Age rules
    if cattle_age < 1.2:
        score = 30.0
        penalties.append(f"Immature heifer (Age: {cattle_age:.1f} years, breeding recommended > 1.2 years)")
        return round(score), penalties, explanations
        
    elif cattle_age >= 1.2 and cattle_age < 2.2:
        # Heifer maturity phase
        score = 70.0
        explanations.append(f"Mature heifer (Age: {cattle_age:.1f} years). Ready for first breeding.")
        
        # Check if heat detected
        heats = [b for b in breeding_history if b['event_type'] == 'heat']
        if heats:
            score += 15
            explanations.append("Active estrus cycles recorded (Great candidate)")
            
    elif cattle_age >= 2.2 and cattle_age < 8.0:
        # Prime breeding cows
        score = 75.0
        explanations.append(f"Cow in prime reproductive age ({cattle_age:.1f} years)")
        
        calvings = [b for b in breeding_history if b['event_type'] == 'calving']
        if calvings:
            # Check last calving interval
            last_calving = calvings[0]
            if last_calving['calving_interval_days'] is not None:
                interval = last_calving['calving_interval_days']
                if interval <= 380:
                    score += 15
                    explanations.append(f"Ideal calving interval ({interval} days)")
                elif interval <= 450:
                    score += 5
                    explanations.append(f"Acceptable calving interval ({interval} days)")
                else:
                    score -= 15
                    penalties.append(f"Prolonged calving interval ({interval} days)")
            else:
                score += 5
                explanations.append("Has successful calving history")
        else:
            # Mature but no calving records
            if cattle_age >= 3.5:
                score -= 25
                penalties.append("Mature age (> 3.5 years) with no calving history")
            else:
                explanations.append("Mature heifer, ready for first calving cycle")
                
    else:
        # Old cows
        score = 35.0
        penalties.append(f"Advanced age ({cattle_age:.1f} years), reduced fertility")
        
    # Check for recent heat (within last 30 days)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    recent_heats = [b for b in breeding_history if b['event_type'] == 'heat' and b['record_date'] >= thirty_days_ago]
    if recent_heats:
        score += 10
        explanations.append("Estrus (heat) detected in the last 30 days")
        
    score = max(0.0, min(100.0, score))
    return round(score), penalties, explanations

def run_decision_engine(cattle_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Retrieve core profile
    cursor.execute("SELECT * FROM cattle WHERE id = ?", (cattle_id,))
    cattle = cursor.fetchone()
    if not cattle:
        conn.close()
        return None
        
    # Execute Modules
    health_score, health_penalties, health_exp = calculate_health_score(cattle_id, cursor)
    prod_score, prod_penalties, prod_exp = calculate_productivity_score(cattle_id, cursor)
    econ_score, econ_penalties, econ_exp = calculate_economic_score(cattle_id, cursor)
    breed_score, breed_penalties, breed_exp = calculate_breeding_score(cattle_id, cursor)
    
    # Weighted Decision Logic
    # 30% Health, 30% Productivity, 25% Economic, 15% Breeding
    weighted_score = (health_score * 0.30) + (prod_score * 0.30) + (econ_score * 0.25) + (breed_score * 0.15)
    
    # Adjustments and Global Risks
    global_penalties = []
    overall_penalty = 0.0
    
    # Check vaccination status recency
    cursor.execute("""
        SELECT record_date FROM health_records 
        WHERE cattle_id = ? AND record_type = 'vaccination'
        ORDER BY record_date DESC LIMIT 1
    """, (cattle_id,))
    latest_vaccine = cursor.fetchone()
    vaccine_overdue = False
    
    if latest_vaccine:
        vaccine_date = datetime.strptime(latest_vaccine['record_date'], "%Y-%m-%d")
        if (datetime.now() - vaccine_date).days > 365:
            vaccine_overdue = True
    else:
        if cattle['age'] > 0.5:
            vaccine_overdue = True
            
    if vaccine_overdue:
        overall_penalty += 5.0
        global_penalties.append("Vaccination Overdue Alert")
        
    # Check for declining milk
    if "Declining milk production" in prod_penalties or "Severely declining milk production" in prod_penalties:
        overall_penalty += 8.0
        global_penalties.append("Declining Milk Yield Alert")
        
    # Check for sudden drop
    if "Sudden drop in productivity detected" in prod_penalties:
        overall_penalty += 12.0
        global_penalties.append("Sudden Milk Drop Alert")
        
    # Check for high medical expense or maintenance cost
    if "High daily housing/labor maintenance overhead" in econ_penalties or "High daily veterinary expense amortization" in econ_penalties:
        overall_penalty += 7.0
        global_penalties.append("High Maintenance Overhead Alert")
        
    # Check for missing health records
    cursor.execute("SELECT COUNT(*) as cnt FROM health_records WHERE cattle_id = ?", (cattle_id,))
    if cursor.fetchone()['cnt'] == 0:
        overall_penalty += 5.0
        global_penalties.append("Missing Health History Alert")
        
    overall_score = max(0.0, weighted_score - overall_penalty)
    
    # Confidence Level
    # Calculate how complete the records are
    cursor.execute("SELECT COUNT(*) as count_p FROM production_records WHERE cattle_id = ?", (cattle_id,))
    count_prod = cursor.fetchone()['count_p']
    
    cursor.execute("SELECT COUNT(*) as count_f FROM financial_records WHERE cattle_id = ?", (cattle_id,))
    count_fin = cursor.fetchone()['count_f']
    
    cursor.execute("SELECT COUNT(*) as count_h FROM health_records WHERE cattle_id = ?", (cattle_id,))
    count_health = cursor.fetchone()['count_h']
    
    confidence = 0.0
    confidence += min(count_prod, 30) / 30.0 * 40.0
    confidence += min(count_fin, 30) / 30.0 * 30.0
    confidence += 20.0 if count_health > 0 else 5.0 # Low confidence penalty for missing health history
    confidence += 10.0 if cattle['age'] > 1.0 else 5.0
    confidence = min(100.0, confidence)
    
    # Recommendations Logic
    # 1. Continue Dairy Production
    # 2. Breeding Candidate
    # 3. Monitor Closely
    # 4. Consider Sale
    
    recommendation = "Monitor Closely"
    explanation_bullets = []
    
    # Combine explanation strings from modules
    all_explanations = health_exp + prod_exp + econ_exp + breed_exp
    all_penalties = health_penalties + prod_penalties + econ_penalties + breed_penalties
    
    # Recommendation logic flow
    if overall_score >= 76.0:
        # High scoring cattle are either prime dairy or breeding candidates
        if breed_score >= 78.0 and 1.5 <= cattle['age'] <= 7.0:
            recommendation = "Breeding Candidate"
            explanation_bullets.append("Excellent reproductive profile and physical health make this cattle ideal for breeding.")
        else:
            recommendation = "Continue Dairy Production"
            explanation_bullets.append("Strong milk yield, high economic return, and general health indicate continuing dairy production.")
    elif overall_score >= 50.0:
        # Moderate scores
        if "Sudden drop in productivity detected" in prod_penalties or "Illness in the last 7 days" in health_penalties:
            recommendation = "Monitor Closely"
            explanation_bullets.append("Recent drop in productivity or active illness requires veterinary monitoring.")
        elif vaccine_overdue:
            recommendation = "Monitor Closely"
            explanation_bullets.append("Vaccination is overdue. Monitor and administer booster doses promptly.")
        elif cattle['age'] < 2.0:
            # Young animal is growing
            if breed_score >= 75.0:
                recommendation = "Breeding Candidate"
                explanation_bullets.append("Developing young heifer showing strong maturity signs.")
            else:
                recommendation = "Continue Dairy Production"
                explanation_bullets.append("Young growing heifer under investment cycle.")
        else:
            recommendation = "Monitor Closely"
            explanation_bullets.append("Marginal economic return or slight productivity declines require observation.")
    else:
        # Low scores (< 50)
        if "Sudden drop in productivity detected" in prod_penalties or "Illness in the last 7 days" in health_penalties:
            recommendation = "Monitor Closely"
            explanation_bullets.append("Recent acute illness or sudden productivity drop detected. Monitor closely and provide veterinary treatment before deciding on a sale.")
        elif econ_score <= 40.0 and cattle['age'] >= 2.0:
            recommendation = "Consider Sale"
            explanation_bullets.append("Uneconomical operation: the animal's maintenance and medical costs outweigh its market returns.")
        elif health_score <= 40.0:
            recommendation = "Consider Sale"
            explanation_bullets.append("Chronic health vulnerabilities and low response to treatments lower long-term value.")
        else:
            recommendation = "Consider Sale"
            explanation_bullets.append("Declining overall health and productivity indices make keeping the animal economically inefficient.")
            
    conn.close()
    
    return {
        "cattle_id": cattle_id,
        "name": cattle["name"],
        "age": cattle["age"],
        "breed": cattle["breed"],
        "status": cattle["status"],
        "market_value": cattle["current_market_value"],
        "health_score": health_score,
        "health_penalties": health_penalties,
        "health_explanations": health_exp,
        "productivity_score": prod_score,
        "productivity_penalties": prod_penalties,
        "productivity_explanations": prod_exp,
        "economic_score": econ_score,
        "economic_penalties": econ_penalties,
        "economic_explanations": econ_exp,
        "breeding_score": breed_score,
        "breeding_penalties": breed_penalties,
        "breeding_explanations": breed_exp,
        "overall_score": round(overall_score, 1),
        "confidence_level": round(confidence),
        "global_alerts": global_penalties,
        "recommendation": recommendation,
        "explanation": explanation_bullets,
        "all_explanations": all_explanations,
        "all_penalties": all_penalties
    }
