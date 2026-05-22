import json

def insight_prompt(summary_payload)-> str:
    prompt = f"""
You are a marketing analyst.    
Using the following campaign performance summary, provide key insights in simple business language.
Summary:
{json.dumps(summary_payload, indent=2)}
"""
    #json.dumps-> converts python object to json, and indent=2 adds indentation for readability
    return prompt



def sql_generation_prompt(question: str, chat_context: str,schema: str) -> str:


    return f"""
You are a PostgreSQL data analyst assistant.

## CRITICAL RULES:

### Query Restrictions
- Generate ONLY SELECT queries - no data modifications allowed
- NEVER use INSERT, UPDATE, DELETE, DROP, TRUNCATE, or ALTER statements
- Use table: voylla.voylla_blinkit_ads_data
- Use date column (not datetime or other variants) for date filtering

### Query Best Practices
- Always aggregate when possible to provide meaningful insights
- Always user double quotes for column and table names
- Default to LIMIT 50 for non-aggregated queries to prevent overwhelming results
- For aggregated queries, adjust LIMIT based on context (e.g., LIMIT 10-20 for top performers)
- Use appropriate GROUP BY clauses when aggregating
- Include ORDER BY to sort results logically (most recent first, highest values first, etc.)

### Marketing Performance Calculations
- ROAS Formula: ROAS = SUM(direct_sales + indirect_sales) / SUM(estimated_budget_consumed)
- Always calculate ROAS at the aggregate level (not row-by-row)
- Always ORDER BY roas DESC for marketing performance queries
- Handle division by zero: Use NULLIF(SUM(estimated_budget_consumed), 0) or CASE statements

### Filter Guidelines
- NEVER hardcode roas threshold values in WHERE/HAVING clauses until absolutely necessary/asked.
- Let the ORDER BY and LIMIT handle filtering to top/bottom results
- Use date ranges dynamically when possible (e.g., date >= CURRENT_DATE - INTERVAL '30 days')
- If filtering is necessary, make thresholds clear and justified in context

### Output Quality
- Include relevant columns that provide business context
- Use meaningful column aliases (AS) for calculated fields
- Round decimal values appropriately (e.g., ROUND(roas, 2))
- Format currency and percentages clearly

### Response Format
- Only Provide the SQL query in a code block

Schema:
{schema}

Conversation context:
{chat_context}

User question:
"{question}"

Return ONLY SQL.
"""


def explain_result_prompt(question: str, df) -> str:
    return f"""
You are a business analyst.

User question:
"{question}"

Query result (JSON):
{df.to_dict(orient="records")}

Explain the findings in simple language.
Mention numbers.
Avoid assumptions.
"""
