import anthropic
import re
import pandas as pd


### Last edited: 10/05/2026
### This script sets up the RAG logic for the initial version of version of our AI model integration


### Initialize our client 
client = anthropic.Anthropic()


# Bring in our data and extract the names of all the food groups that contain data points
path = "/Volumes/trevor_external/capstone-backend/backend/app/data/env_impact_of_food_scored.csv"
df = pd.read_csv(path)

FOOD_NAMES = df["entity"].tolist()



### Create our methodology note so that the model can accurately respond to narrative-framed questions
# EX: "How can I trust this data?"

METHODOLOGY_NOTE = """
This data is drawn from Poore & Nemecek (2018), a meta-analysis of ~38,000 farms
across 119 countries, published by Our World in Data. Figures are GLOBAL AVERAGES
per kilogram of product, pinned to a 2010 reference year — not a specific grocery
item, country, or production method (e.g. grass-fed vs. feedlot beef). The
Environmental Impact Score combines four metrics (GHG emissions, land use,
eutrophying emissions, and scarcity-weighted water use) using a weighted
geometric mean, with weights sourced from the EU's Product Environmental
Footprint (PEF) methodology. Treat results as directional and comparative,
not precise or personalized.
"""



### Food Keyword Matching
# Find if any foods from our list of food entities in our data can be found within the user's query

# Extract the matching foods from our food list from the user's query
def match_foods(query): 
    # Extract all full words from user query, returns list of words
    q_words = re.findall(r"[a-z+]", query.lower())
    
    matched = []
    # Iterate through all food category names within our df
    for name in FOOD_NAMES: 
        # Drop any abbreviated specifications for food like "Beef (dairy)" -> "beef"
        base = re.sub(r"/(.*?/)", "", name)
        
        # Set iterator that returns a all food names without any excess characters like trailing spaces
        name_words = {w for w in re.findall(r"[a-z]+", base) if len(w) > 2}
        
        # A conditional that checks if the food group name is in the user's query
        # or if there are other values-in-common in or food name set and the list of words from the query
        if name.lower() in query.lower() or name_words & q_words: 
            matched.append(name)
    
    
    
### Router
# This decides what recourses Claude needs in order to effectively respond to a user. It does this with plain string
# search to save a model call. 
# Structured = Requires quantitative data to respond. Look up our dataset
# Narrative = Requires our methodology note to effectively respond
# Both = Both the data and our methodology note to respond

STRUCTURED_KEYWORDS = ["compare", " vs ", "versus", "higher", "lower", "highest",
                        "lowest", "rank", "worse", "better", "which is", "more than"]
NARRATIVE_KEYWORDS = ["why", "should i", "how reliable", "trust", "accurate",
                    "methodology", "confidence", "source"]

def route_query(query): 
    # Standardize the casing of the user query
    q = query.lower()
    # Return true if any of the structured keywords are in the user query or match_food returned list contains any values
    wants_structured = any(k in q for k in STRUCTURED_KEYWORDS) or len(match_foods(query)) >= 1
    # Return true if any narrative keywords found within the user query
    wants_narrative = any(k in q for k in NARRATIVE_KEYWORDS)
    if wants_structured and wants_narrative: 
        return "both"
    return "narrative" if wants_narrative else "structured"



### Context Assembly
# Takes the label from route_query and translates it to text so that Claude can read it. Claude can only 
# read text, so the query and any required information from our data must be first converted to text
# prior to being sent to Claude

DISPLAY_COLS = ["entity", "ghg_kg_co2eq_per_kg", "land_use_m2_per_kg",
                "eutrophying_emissions_g_po4eq_per_kg",
                "scarcity_weighted_water_l_per_kg", "environmental_impact_score"]

# If applicable, get the relevant rows from our data and then convert them to a string to appended to our 
# context in the next function
def structured_context(query): 
    # Get our list of matched foods from the user query
    foods = match_foods(query)
    # If no foods found, return this string context to say so
    if not foods: 
        return "No specific foods matched in the dataset for this query."
    # Create a subset of rows that contain the data corresponding to the matched foods from the user query
    subset = df[df["entity"]].isin(foods)[DISPLAY_COLS]
    # Convert the data to a string 
    return "RELEVANT DATA:\n" + subset.to_string(index=False)

# Build the final context to provide our model
def build_context(query, route): 
    parts = []
    # If we need structured data to accurately respond, create it then append it
    if route in ("structured", "both"): 
        parts.append(structured_context(query))
    # If we need methodology notes, add them
    if route in ("narrative", "both"): 
        parts.append("METHODOLOGY NOTES: \n" + METHODOLOGY_NOTE)
    # Join all parts with double line spacing between all bodies
    return "\n\n".join(parts)



# Create the prompt for the model and send it

SYSTEM_PROMPT = (
    "You answer questions about the environmental impact of food using the "
    "Poore & Nemecek (2018) / Our World in Data dataset and the Environmental "
    "Impact Score computed from it. Use the provided data when given, and be "
    "precise with numbers in comparisons. When a question is interpretive or "
    "about reliability, weave in the methodology caveats naturally rather than "
    "overclaiming precision. Keep answers concise and conversational."
)


# Put it all together
def answer_question(query): 
    route = route_query(query)
    context = build_context(query, route)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024, 
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"{context}\n\nQuestion: {query}"}]
        
    )
    return message.content[0].text
    
