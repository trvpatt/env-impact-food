from fastapi import FastAPI, HTTPException
import httpx

# Initialize our API
app = FastAPI()

@app.get("/")
def read_root(): 
    return {"Hello": "World"}



open_food_facts_headers = {"User-Agent": "CapstoneApp/1.0 (trvpattft@gmail.com)"}

@app.get("/foods/{barcode}")
async def get_food(barcode: str): 
    
    url = f"https://world.openfoodfacts.org/api/v3.6/product/{barcode}.json"
    
    try: 
        async with httpx.AsyncClient() as client: 
            response = await client.get(url, headers=open_food_facts_headers,timeout=5)
            response.raise_for_status()

    except httpx.TimeoutException: 
        raise HTTPException(status_code= 502, detail="Open food facts request timed out")
    except httpx.ConnectError: 
        raise HTTPException(status_code=502, detail="Could not reach open food facts")
    except httpx.RequestError as e: 
        raise HTTPException(status_code=502, detail=f"Upstream request failed: {e}")
    
    if response.is_success: 
        return response.json()
    else: 
        raise HTTPException(status_code=502, detail=f"Open food facts returned {response}")