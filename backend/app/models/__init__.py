"""Database tables. Importing this package registers every table on `SQLModel.metadata`."""

from app.models.billing import PaymentMethod, Plan, Subscription
from app.models.content import Article, Conversation, ConversationMessage, SupportTicket
from app.models.food import Food, ShoppingList, ShoppingListItem
from app.models.place import CommunityOrg, FavoriteRestaurant, LocalFoodPlace, Restaurant
from app.models.recipe import FavoriteRecipe, Recipe, RecipeIngredient
from app.models.reference import Avatar, Cuisine, PostalCode, Quote
from app.models.user import (
    EmailToken,
    EmailTokenPurpose,
    LoginChallenge,
    RateLimitHit,
    RefreshToken,
    Survey,
    User,
)

__all__ = [
    "Article",
    "Avatar",
    "CommunityOrg",
    "Conversation",
    "ConversationMessage",
    "Cuisine",
    "EmailToken",
    "EmailTokenPurpose",
    "FavoriteRecipe",
    "FavoriteRestaurant",
    "Food",
    "LocalFoodPlace",
    "LoginChallenge",
    "PaymentMethod",
    "Plan",
    "PostalCode",
    "Quote",
    "RateLimitHit",
    "Recipe",
    "RecipeIngredient",
    "RefreshToken",
    "Restaurant",
    "ShoppingList",
    "ShoppingListItem",
    "Subscription",
    "SupportTicket",
    "Survey",
    "User",
]
