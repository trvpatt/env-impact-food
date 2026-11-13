import hashlib
import hmac
import json
import time
from datetime import date, timedelta

from app.models import (
    Article,
    Cuisine,
    Food,
    LocalFoodPlace,
    Plan,
    PostalCode,
    Quote,
    Recipe,
    RecipeIngredient,
    Restaurant,
)
from app.models.base import utcnow

ADDRESS = {
    "line1": "1 Main St",
    "city": "Austin",
    "state": "TX",
    "postal_code": "78701",
    "country": "US",
}


def seed(db):
    db.add(
        Cuisine(
            id="indian", name="Indian", image_url="https://img.test/curry.jpg", country_code="IN"
        )
    )
    db.add(
        Cuisine(
            id="italian", name="Italian", image_url="https://img.test/pasta.jpg", country_code="IT"
        )
    )
    db.add(
        Food(
            id="lentils",
            name="Lentils",
            category="Legumes",
            nutrients_per_100g=[
                {"name": "Protein", "amount": 25, "unit": "g"},
                {"name": "Fiber, total dietary", "amount": 11, "unit": "g"},
            ],
            co2e_kg_per_kg=0.9,
            water_liters_per_kg=100,
            land_m2_per_kg=3.4,
            avg_price_cents_per_kg=400,
        )
    )
    db.add(PostalCode(code="78701", lat=30.27, lng=-97.74))
    db.commit()


def test_survey_flow(client, db, auth):
    seed(db)
    assert client.get("/users/me/survey", headers=auth).status_code == 404
    response = client.post("/users/me/survey/complete", headers=auth)
    assert response.status_code == 422
    assert {e["field"] for e in response.json()["field_errors"]} == {
        "diet",
        "cuisine_ids",
        "health_goals",
        "motivations",
    }

    response = client.patch("/users/me/survey", headers=auth, json={"cuisine_ids": ["martian"]})
    assert response.json()["field_errors"][0]["code"] == "INVALID_VALUE"

    response = client.patch(
        "/users/me/survey",
        headers=auth,
        json={
            "diet": "vegan",
            "cuisine_ids": ["indian", "indian"],
            "health_goals": ["build_muscle"],
            "motivations": ["environment"],
        },
    )
    assert response.json()["cuisine_ids"] == ["indian"]
    response = client.post("/users/me/survey/complete", headers=auth)
    assert response.json()["completed_at"] is not None
    me = client.get("/users/me", headers=auth).json()
    assert me["onboarding_completed"] is True
    assert me["diet"] == "vegan"

    options = client.get("/reference/survey-options").json()
    assert [c["id"] for c in options["cuisines"]] == ["indian", "italian"]


def test_shopping_lists_and_impact(client, db, auth):
    seed(db)
    client.patch("/users/me/survey", headers=auth, json={"health_goals": ["build_muscle"]})
    body = {
        "name": "Weekly shop",
        "purchased_on": date.today().isoformat(),
        "items": [{"food_id": "lentils", "quantity": 2, "unit": "kg", "price_cents": 700}],
    }
    response = client.post(
        "/shopping-lists",
        headers=auth,
        json={**body, "items": [{"food_id": "nope", "quantity": 1, "unit": "cup"}]},
    )
    assert {e["field"] for e in response.json()["field_errors"]} == {
        "items.0.food_id",
        "items.0.unit",
    }

    response = client.post("/shopping-lists", headers=auth, json=body)
    assert response.status_code == 201
    sl = response.json()
    assert sl["items"][0]["food_name"] == "Lentils"

    page = client.get("/shopping-lists", headers=auth).json()
    assert [s["id"] for s in page["items"]] == [sl["id"]]
    assert page["next_cursor"] is None

    weekly = client.get("/home/weekly-impact", headers=auth).json()
    # 2 kg x (3.0 baseline - 0.9) kg CO2e
    assert weekly["environmental"]["co2e_kg_saved"] == 4.2
    assert weekly["money_saved"]["amount_cents"] == 2 * 900 - 700
    assert weekly["health"]["protein_g"] == 500
    assert weekly["health"]["goal_progress"][0]["goal"] == "build_muscle"

    report = client.get("/reports/me", headers=auth, params={"period": "year"}).json()
    assert len(report["series"]) == 12
    assert report["environmental"]["co2e_kg_saved"] == 4.2

    response = client.put(f"/shopping-lists/{sl['id']}", headers=auth, json={**body, "items": []})
    assert response.json()["items"] == []
    assert client.delete(f"/shopping-lists/{sl['id']}", headers=auth).status_code == 204
    assert client.get(f"/shopping-lists/{sl['id']}", headers=auth).status_code == 404


def test_pagination(client, db, auth):
    seed(db)
    for n in range(3):
        client.post("/shopping-lists", headers=auth, json={"name": f"List {n}", "items": []})
    first = client.get("/shopping-lists", headers=auth, params={"limit": 2}).json()
    assert [s["name"] for s in first["items"]] == ["List 2", "List 1"]
    second = client.get(
        "/shopping-lists", headers=auth, params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert [s["name"] for s in second["items"]] == ["List 0"]
    assert second["next_cursor"] is None
    bad = client.get("/shopping-lists", headers=auth, params={"cursor": "garbage"})
    assert bad.status_code == 422


def test_foods(client, db, auth):
    seed(db)
    assert [f["id"] for f in client.get("/foods", headers=auth, params={"q": "lent"}).json()] == [
        "lentils"
    ]
    assert client.get("/foods/lentils", headers=auth).json()["co2e_kg_per_kg"] == 0.9
    assert client.get("/foods/missing", headers=auth).status_code == 404


def test_recipes(client, db, auth):
    seed(db)
    curry = Recipe(
        title="Dal",
        image_url="https://img.test/dal.jpg",
        cuisine_id="indian",
        diets=["vegan"],
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=30,
        steps=["Cook"],
    )
    pasta = Recipe(
        title="Pasta",
        image_url="https://img.test/p.jpg",
        cuisine_id="italian",
        diets=["vegetarian"],
        servings=2,
        steps=["Boil"],
    )
    db.add_all([curry, pasta])
    db.flush()
    db.add_all(
        [
            RecipeIngredient(
                recipe_id=curry.id,
                position=0,
                food_id="lentils",
                name="red lentils",
                display_text="1 cup red lentils",
            ),
            RecipeIngredient(
                recipe_id=curry.id, position=1, name="garlic", display_text="2 cloves garlic"
            ),
            RecipeIngredient(
                recipe_id=pasta.id, position=0, name="garlic", display_text="1 clove garlic"
            ),
        ]
    )
    db.commit()

    response = client.get("/recipes", headers=auth, params={"favorites_only": True})
    assert response.status_code == 409
    assert response.json()["code"] == "NO_FAVORITE_RECIPES"

    response = client.get("/recipes", headers=auth, params={"ingredients": "garlic;lentils"})
    assert response.json()["field_errors"][0]["code"] == "INVALID_INGREDIENT_FORMAT"

    results = client.get(
        "/recipes", headers=auth, params={"ingredients": "lentils, garlic"}
    ).json()["items"]
    assert [(r["title"], r["matched_ingredient_count"]) for r in results] == [
        ("Dal", 2),
        ("Pasta", 1),
    ]

    assert [
        r["title"]
        for r in client.get("/recipes", headers=auth, params={"diet": "vegan"}).json()["items"]
    ] == ["Dal"]
    assert [
        r["title"]
        for r in client.get("/recipes", headers=auth, params={"cuisine_ids": "italian"}).json()[
            "items"
        ]
    ] == ["Pasta"]

    assert client.put(f"/users/me/favorites/recipes/{curry.id}", headers=auth).status_code == 204
    assert client.put(f"/users/me/favorites/recipes/{curry.id}", headers=auth).status_code == 204
    favorites = client.get("/users/me/favorites/recipes", headers=auth).json()["items"]
    assert [r["title"] for r in favorites] == ["Dal"]

    detail = client.get(f"/recipes/{curry.id}", headers=auth).json()
    assert detail["is_favorite"] is True
    assert detail["total_time_minutes"] == 40
    assert [i["display_text"] for i in detail["ingredients"]][0] == "1 cup red lentils"

    big = client.get("/home/big-picture", headers=auth).json()
    assert big["featured_recipes"][0]["title"] == "Dal"

    assert client.delete(f"/users/me/favorites/recipes/{curry.id}", headers=auth).status_code == 204
    assert client.delete(f"/users/me/favorites/recipes/{curry.id}", headers=auth).status_code == 204


def test_places(client, db, auth):
    seed(db)
    hours = [{"day_of_week": 0, "opens": "09:00", "closes": "17:00"}]
    db.add(
        Restaurant(
            id="r1",
            name="Green Bowl",
            address=ADDRESS,
            lat=30.28,
            lng=-97.74,
            hours=hours,
            cuisine_ids=["indian"],
            diets_supported=["vegan", "vegetarian"],
        )
    )
    db.add(
        Restaurant(
            id="r2",
            name="Far Away",
            address=ADDRESS,
            lat=32.0,
            lng=-97.74,
            diets_supported=["vegan"],
        )
    )
    db.add(
        LocalFoodPlace(
            id="m1", name="Market", address=ADDRESS, lat=30.27, lng=-97.75, type="farmers_market"
        )
    )
    db.commit()

    response = client.get("/restaurants/search", headers=auth, params={"diet": "vegan"})
    assert response.json()["code"] == "LOCATION_REQUIRED"
    response = client.get(
        "/restaurants/search", headers=auth, params={"diet": "vegan", "postal_code": "99999"}
    )
    assert response.json()["code"] == "UNKNOWN_POSTAL_CODE"

    page = client.get(
        "/restaurants/search",
        headers=auth,
        params={"diet": "vegan", "postal_code": "78701", "radius_miles": 25},
    ).json()
    assert [r["id"] for r in page["items"]] == ["r1"]
    assert page["search_center"] == {"lat": 30.27, "lng": -97.74}
    assert (
        client.get(
            "/restaurants/search",
            headers=auth,
            params={"diet": "vegan", "lat": 30.27, "lng": -97.74, "radius_miles": 15},
        ).status_code
        == 422
    )

    assert client.put("/users/me/favorites/restaurants/r1", headers=auth).status_code == 204
    assert client.put("/users/me/favorites/restaurants/nope", headers=auth).status_code == 404
    assert client.get("/restaurants/r1", headers=auth).json()["is_favorite"] is True

    # Local food falls back to the user's saved address.
    assert (
        client.get("/local-food/search", headers=auth, params={"types": "coop"}).json()["code"]
        == "LOCATION_REQUIRED"
    )
    client.patch("/users/me", headers=auth, json={"address": ADDRESS})
    page = client.get(
        "/local-food/search", headers=auth, params={"types": "farmers_market,coop"}
    ).json()
    assert [p["type"] for p in page["items"]] == ["farmers_market"]
    response = client.get("/community/search", headers=auth, params={"types": "bakery"})
    assert response.json()["field_errors"][0]["code"] == "INVALID_VALUE"
    assert (
        client.get("/community/search", headers=auth, params={"types": "food_pantry"}).json()[
            "items"
        ]
        == []
    )


def test_content_and_quote(client, db, auth):
    db.add(
        Article(
            id="a1",
            title="Soil",
            summary="s",
            url="https://news.test/soil",
            topic="soil",
            published_at=utcnow(),
        )
    )
    db.add(
        Article(
            id="a2",
            title="Water",
            summary="s",
            url="https://news.test/water",
            topic="water",
            published_at=utcnow() - timedelta(days=1),
        )
    )
    db.add(Quote(text="Eat more plants."))
    db.commit()
    assert [a["id"] for a in client.get("/articles", headers=auth).json()["items"]] == ["a1", "a2"]
    assert [
        a["id"]
        for a in client.get("/articles", headers=auth, params={"topic": "water"}).json()["items"]
    ] == ["a2"]
    quote = client.get("/home/daily-quote", headers=auth).json()
    assert quote["text"] == "Eat more plants."
    assert quote["date"] == date.today().isoformat()


def test_assistant(client, fakes, auth):
    conversation = client.post("/assistant/conversations", headers=auth).json()
    url = f"/assistant/conversations/{conversation['id']}/messages"

    response = client.post(url, headers=auth, json={"content": "Dinner ideas?"})
    assert response.status_code == 200
    assert response.json()["role"] == "assistant"
    assert response.json()["content"] == "Try lentil soup."
    system, messages = fakes.model.calls[-1]
    assert "Name: Ada" in system
    assert messages == [{"role": "user", "content": "Dinner ideas?"}]

    with client.stream(
        "POST", url, headers={**auth, "Accept": "text/event-stream"}, json={"content": "More?"}
    ) as stream:
        body = "".join(stream.iter_text())
    assert body.count("event: delta") == 3
    assert "event: done" in body

    history = client.get(url, headers=auth).json()["items"]
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
    listed = client.get("/assistant/conversations", headers=auth).json()["items"]
    assert listed[0]["title"] == "Dinner ideas?"

    other = "/assistant/conversations/00000000-0000-0000-0000-000000000000/messages"
    assert client.post(other, headers=auth, json={"content": "hi"}).status_code == 404


def test_support(client, auth):
    response = client.post(
        "/support/bug-reports", headers=auth, json={"description": "The map is blank on Safari."}
    )
    assert response.status_code == 201
    assert (
        client.post(
            "/support/contact", headers=auth, json={"subject": "Hi", "message": "Hello"}
        ).status_code
        == 201
    )
    assert (
        client.post("/support/bug-reports", headers=auth, json={"description": "short"}).status_code
        == 422
    )


def test_billing(client, db, auth):
    db.add(
        Plan(id="free", name="Free", price_cents=0, interval="month", features=["Impact tracking"])
    )
    db.add(
        Plan(
            id="plus", name="Plus", price_cents=499, interval="month", provider_price_id="price_123"
        )
    )
    db.commit()
    assert [p["id"] for p in client.get("/billing/plans").json()] == ["free", "plus"]
    assert client.get("/billing/subscription", headers=auth).status_code == 404

    response = client.post("/billing/subscription", headers=auth, json={"plan_id": "plus"})
    assert response.status_code == 402
    assert response.json()["code"] == "PAYMENT_REQUIRED"

    sub = client.post("/billing/subscription", headers=auth, json={"plan_id": "free"}).json()
    assert sub["plan"]["id"] == "free"
    assert sub["status"] == "active"
    assert client.post("/billing/subscription/cancel", headers=auth).json()["status"] == "canceled"
    assert client.get("/billing/payment-method", headers=auth).status_code == 404


def test_webhook_signature(client):
    payload = json.dumps(
        {"type": "customer.subscription.updated", "data": {"object": {"customer": "cus_unknown"}}}
    )
    assert (
        client.post(
            "/billing/webhook", content=payload, headers={"Stripe-Signature": "t=1,v1=bad"}
        ).status_code
        == 400
    )

    t = int(time.time())
    sig = hmac.new(b"whsec_test", f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    response = client.post(
        "/billing/webhook", content=payload, headers={"Stripe-Signature": f"t={t},v1={sig}"}
    )
    assert response.status_code == 200
