# Env Impact Food

A web experience for exploring the environmental impact of food, finding nearby
vegan and vegetarian-friendly restaurants, and discovering plant-forward recipes.

## Run the web UI and Google Places backend

Use Python 3.10 or newer for the backend. Create the virtual environment with
that interpreter (for example, replace `python3.11` below with your installed
Python 3.10+ executable).

The Google Places API key must stay on the backend; do not add it to frontend
files or commit it. Create a Google Cloud API key with **Places API (New)**
enabled and billing configured, then restrict it to Places API.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
export GOOGLE_PLACES_API_KEY="your-google-places-key"
python -m uvicorn backend.places_api:app --reload --port 8000
```

Then open <http://localhost:8000>. Do not open `index.html` directly as a
`file://` URL: the browser can't reach the Places backend that way. If the
backend is running but Places returns a configuration error, set
`GOOGLE_PLACES_API_KEY` in the same terminal before starting Uvicorn.

## Interface preview

The landing page and navigation are a front-end prototype based on the product
specification. Use **Explore the app** to open the optional, step-by-step
preferences survey and demo dashboard. Sign-in, sign-up, CAPTCHA, email
verification, payment processing, and account settings are not connected.
Survey answers remain in page memory; favorite recipes and restaurants are
saved only in this browser's local storage. Dashboard and report figures are
illustrative examples.

- Recipe discovery uses TheMealDB's public API. Cuisine and ingredient searches
  compare the recipe's listed ingredients with vegetarian/vegan exclusions.
  Mediterranean is a broad label and isn't an ingredient-level nutrition or
  dietary certification;
  ingredient searches require comma-separated values. Selecting a result opens
  an in-page preview with favorite and print controls and a link to the original
  recipe. Always check the linked recipe for full dietary details.
- Nearby restaurant search sends coordinates or a city/ZIP query to the backend,
  along with the selected vegan, vegetarian, or Mediterranean preference, optional cuisine, and
  search radius. The backend searches Google Places Text Search (New). The API
  key is never sent to the browser. Coordinate searches apply the radius as a
  location bias; city/ZIP searches add it to the natural-language query, so
  Google may not enforce an exact boundary. Results can be shown on a map or in
  a printable list. The map is a Google Maps embed.
  Restrict a deployed key to the server's outbound IP address and Places API,
  and set quota/billing alerts in Google Cloud.
- Google Places provides general text-search matches, not verified dietary
  offerings. Confirm options with each restaurant.
- Local-food and community searches use the backend's `/api/places/directory-search`
  endpoint and offer map and printable list views. Search results are Google
  Places text matches, not complete or independently verified directories;
  Google may not enforce exact radius boundaries. Missing hours and contact
  details are identified as not listed by Google. USDA and other directory links
  remain available as external starting points.
- The Explore cost comparison is based on a 2021 modelling study covering
  150 countries and 2017 food prices. Its full-cost analysis includes estimated
  climate-change and diet-related health-care costs; it is not a current local
  grocery-price estimate. Sources are linked in the Explore comparison.
- Recipe cards open an in-app detail preview with a link to the original source.

The interface is built with static HTML, CSS, and JavaScript; the small FastAPI
backend serves the files and proxies Google Places requests.
