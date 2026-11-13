from sqlmodel import Field, SQLModel


class Cuisine(SQLModel, table=True):
    __tablename__ = "cuisines"

    id: str = Field(primary_key=True, max_length=50)
    name: str
    image_url: str
    country_code: str = Field(max_length=2)
    flag_url: str | None = None
    sort_order: int = 0


class Avatar(SQLModel, table=True):
    __tablename__ = "avatars"

    id: str = Field(primary_key=True, max_length=50)
    name: str
    image_url: str
    sort_order: int = 0


class Quote(SQLModel, table=True):
    __tablename__ = "quotes"

    id: int | None = Field(default=None, primary_key=True)
    text: str
    author: str | None = None


class PostalCode(SQLModel, table=True):
    """US ZIP centroid, used to turn `postal_code` into a search center."""

    __tablename__ = "postal_codes"

    code: str = Field(primary_key=True, max_length=5)
    lat: float
    lng: float
