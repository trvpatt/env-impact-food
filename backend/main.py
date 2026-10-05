from fastapi import FastAPI
import httpx
from datetime import datetime
from pydantic import BaseModel
from sqlmodel import Field
from contextlib import asynccontextmanager
from openfoodfacts import ProductDataset



# Set up the access to the food dataset
open_foods_dataset = ProductDataset(dataset_type="csv")


#