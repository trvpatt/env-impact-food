# Env Impact Food

A web experience for exploring the environmental impact of food, finding nearby
vegan and vegetarian-friendly restaurants, and discovering plant-forward recipes.

## Run the web UI and Google Places backend

The Google Places API key must stay on the backend; do not add it to frontend
files or commit it. Create a Google Cloud API key with **Places API (New)**
enabled and billing configured, then restrict it to Places API.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
export GOOGLE_PLACES_API_KEY="your-google-places-key"
python -m uvicorn backend.places_api:app --reload --port 8000
```

Then open <http://localhost:8000>. Do not open `index.html` directly as a
`file://` URL: the browser can't reach the Places backend that way. If the
backend is running but Places returns a configuration error, set
`GOOGLE_PLACES_API_KEY` in the same terminal before starting Uvicorn.

- Recipe discovery uses TheMealDB's public API. Cuisine and ingredient searches
  compare the recipe's listed ingredients with vegetarian/vegan exclusions;
  always check the linked recipe for full dietary details.
- Nearby restaurant search sends coordinates or a city/ZIP query to the backend,
  along with the selected vegan or vegetarian preference. The backend searches
  Google Places Text Search (New). The API key is never sent to the browser.
  Restrict a deployed key to the server's outbound IP address and Places API,
  and set quota/billing alerts in Google Cloud.
- Google Places provides general text-search matches, not verified vegan or
  vegetarian menu information. Confirm dietary options with each restaurant.
- External recipe pages open in a right-side preview where embedding is allowed,
  with a link to open the original source if it is not.

The existing Python backend prototype remains separate from this Places API app.
