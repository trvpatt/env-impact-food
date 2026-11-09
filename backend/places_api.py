import os
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOOGLE_PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_FIELDS = ",".join(
    (
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.googleMapsUri",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.primaryTypeDisplayName",
    )
)

app = FastAPI(title="Env Impact Food Places API")


class PlaceSearchRequest(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    area: str | None = None
    diet: Literal["vegan", "vegetarian"] = "vegetarian"


@app.get("/")
async def read_home() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/app.js")
async def read_app_script() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "app.js", media_type="text/javascript")


@app.get("/styles.css")
async def read_stylesheet() -> FileResponse:
    return FileResponse(PROJECT_ROOT / "styles.css", media_type="text/css")


@app.post("/api/places/search")
async def search_places(request: PlaceSearchRequest) -> dict[str, list[dict[str, Any]]]:
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Google Places is not configured. Set GOOGLE_PLACES_API_KEY on the backend.",
        )

    text_query: str
    body: dict[str, Any] = {"maxResultCount": 20}
    if request.area is not None:
        area = request.area.strip()
        if not area or len(area) > 160:
            raise HTTPException(status_code=400, detail="Enter an area up to 160 characters.")
        text_query = f"{request.diet} restaurants in {area}"
    elif request.latitude is not None and request.longitude is not None:
        if not (-90 <= request.latitude <= 90 and -180 <= request.longitude <= 180):
            raise HTTPException(status_code=400, detail="The coordinates are outside valid ranges.")
        text_query = f"{request.diet} restaurants"
        body["locationBias"] = {
            "circle": {
                "center": {
                    "latitude": request.latitude,
                    "longitude": request.longitude,
                },
                "radius": 10000,
            }
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either a city or coordinates for the place search.",
        )

    body["textQuery"] = text_query

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                GOOGLE_PLACES_URL,
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": api_key,
                    "X-Goog-FieldMask": PLACE_FIELDS,
                },
                json=body,
            )
    except httpx.RequestError as error:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to Google Places. Check the backend's network connection.",
        ) from error

    if not response.is_success:
        if response.status_code in (400, 403):
            detail = (
                "Google Places rejected the request. Confirm Places API (New) is enabled, "
                "billing is active, and the server key is valid."
            )
        elif response.status_code == 429:
            detail = "Google Places quota was exceeded. Check your Google Cloud quota and billing."
        else:
            detail = f"Google Places returned an error (HTTP {response.status_code}). Try again later."
        raise HTTPException(status_code=502, detail=detail)

    try:
        response_data = response.json()
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="Google Places returned an unreadable response. Try again later.",
        ) from error

    if not isinstance(response_data, dict):
        raise HTTPException(
            status_code=502,
            detail="Google Places returned an unexpected response. Try again later.",
        )
    places = response_data.get("places", [])
    if not isinstance(places, list) or any(not isinstance(place, dict) for place in places):
        raise HTTPException(
            status_code=502,
            detail="Google Places returned an unexpected response. Try again later.",
        )

    return {
        "places": [
            {
                "id": place.get("id"),
                "name": place.get("displayName", {}).get("text", "Restaurant"),
                "address": place.get("formattedAddress", ""),
                "latitude": place.get("location", {}).get("latitude"),
                "longitude": place.get("location", {}).get("longitude"),
                "googleMapsUri": place.get("googleMapsUri"),
                "websiteUri": place.get("websiteUri"),
                "rating": place.get("rating"),
                "userRatingCount": place.get("userRatingCount"),
                "primaryType": place.get("primaryTypeDisplayName", {}).get("text"),
            }
            for place in places
        ]
    }
