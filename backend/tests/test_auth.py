from tests.conftest import PASSWORD, signup, years_ago


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_errors_use_spec_shape(client):
    response = client.get("/users/me")
    assert response.status_code == 401
    assert response.json() == {"code": "UNAUTHORIZED", "message": "Authentication required"}


def test_signup_field_errors(client):
    response = signup(
        client,
        email="not-an-email",
        birthday=years_ago(17),
        password="short",
        password_confirm="different",
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert {(e["field"], e["code"]) for e in body["field_errors"]} == {("email", "INVALID_EMAIL")}

    response = signup(
        client, birthday=years_ago(17), password="short", password_confirm="different"
    )
    codes = {(e["field"], e["code"]) for e in response.json()["field_errors"]}
    assert codes == {
        ("birthday", "UNDERAGE"),
        ("password", "WEAK_PASSWORD"),
        ("password_confirm", "PASSWORD_MISMATCH"),
    }

    assert signup(client).status_code == 201
    response = signup(client, email="ADA@example.com")
    assert response.json()["field_errors"][0]["code"] == "EMAIL_IN_USE"


def test_signup_verify_login_captcha(client, fakes):
    assert signup(client).status_code == 201
    verify_token = fakes.email.last_token()

    response = client.post("/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
    assert response.status_code == 403
    assert response.json()["code"] == "EMAIL_NOT_VERIFIED"

    response = client.post("/auth/verify-email", json={"token": verify_token})
    assert response.status_code == 200
    assert "refresh_token" in response.cookies
    assert response.json()["user"]["email_verified"] is True
    # Tokens are single-use.
    assert client.post("/auth/verify-email", json={"token": verify_token}).status_code == 400

    challenge = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": PASSWORD}
    ).json()
    fakes.captcha.ok = False
    response = client.post(
        "/auth/login/captcha",
        json={"challenge_id": challenge["challenge_id"], "captcha_token": "x"},
    )
    assert response.json()["code"] == "CAPTCHA_FAILED"
    fakes.captcha.ok = True
    response = client.post(
        "/auth/login/captcha",
        json={"challenge_id": challenge["challenge_id"], "captcha_token": "x"},
    )
    assert response.status_code == 200
    tokens = response.json()
    assert tokens["token_type"] == "bearer"

    me = client.get("/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.json()["first_name"] == "Ada"
    assert me.json()["onboarding_completed"] is False


def test_lockout_after_three_failures(client, fakes, auth):
    bad = {"email": "ada@example.com", "password": "Wrong-Password-1!"}
    assert client.post("/auth/login", json=bad).json()["attempts_remaining"] == 2
    assert client.post("/auth/login", json=bad).json()["attempts_remaining"] == 1
    response = client.post("/auth/login", json=bad)
    assert response.status_code == 423
    assert response.json()["code"] == "EMAIL_CONFIRMATION_REQUIRED"

    # Even the right password is refused until the emailed link is used.
    good = {"email": "ada@example.com", "password": PASSWORD}
    assert client.post("/auth/login", json=good).status_code == 423
    response = client.post("/auth/login/confirm", json={"token": fakes.email.last_token()})
    assert response.status_code == 200
    assert client.post("/auth/login", json=good).status_code == 200


def test_refresh_rotation_detects_reuse(client, auth):
    old = client.cookies.get("refresh_token")
    assert client.post("/auth/refresh").status_code == 200
    new = client.cookies.get("refresh_token")
    assert new != old

    client.cookies.set("refresh_token", old, path="/api/v1/auth")
    assert client.post("/auth/refresh").status_code == 401
    # Replay of a rotated token revokes the whole family.
    client.cookies.set("refresh_token", new, path="/api/v1/auth")
    assert client.post("/auth/refresh").status_code == 401


def test_password_reset_ends_sessions(client, fakes, auth):
    assert (
        client.post("/auth/password/forgot", json={"email": "nobody@example.com"}).status_code
        == 202
    )
    assert (
        client.post("/auth/password/forgot", json={"email": "ada@example.com"}).status_code == 202
    )
    token = fakes.email.last_token()
    new_password = "An0ther-Strong-Pass!"
    response = client.post(
        "/auth/password/reset",
        json={"token": token, "password": new_password, "password_confirm": new_password},
    )
    assert response.status_code == 204
    assert client.get("/users/me", headers=auth).status_code == 401
    assert client.post("/auth/refresh").status_code == 401
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": new_password}
    )
    assert response.status_code == 200


def test_change_email_requires_confirmation(client, fakes, auth):
    response = client.patch("/users/me", headers=auth, json={"email": "new@example.com"})
    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"
    assert response.json()["pending_email"] == "new@example.com"
    assert fakes.email.sent[-1][0] == "new@example.com"

    response = client.post("/auth/verify-email", json={"token": fakes.email.last_token()})
    assert response.json()["user"]["email"] == "new@example.com"
    assert response.json()["user"]["pending_email"] is None


def test_change_password(client, auth):
    response = client.put(
        "/users/me/password",
        headers=auth,
        json={"current_password": "wrong", "new_password": "x", "new_password_confirm": "x"},
    )
    codes = {e["code"] for e in response.json()["field_errors"]}
    assert codes == {"INCORRECT_PASSWORD", "WEAK_PASSWORD"}
    new_password = "An0ther-Strong-Pass!"
    response = client.put(
        "/users/me/password",
        headers=auth,
        json={
            "current_password": PASSWORD,
            "new_password": new_password,
            "new_password_confirm": new_password,
        },
    )
    assert response.status_code == 204
