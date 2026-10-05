#schemas.py
from pydantic import BaseModel

class FoodSummary(BaseModel): 
    barcode: str
    name: str | None
    brands: str | None
    nutriscore_grade: str | None
    environmental_score_grade: str | None
    
    
    
class FavoriteFood(BaseModel): 
    barcode: str
    note: str | None = None