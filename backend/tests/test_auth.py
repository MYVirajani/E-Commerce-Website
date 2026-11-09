USER = {"email": "ada@shop.dev", "password": "correct-horse", "full_name": "Ada"}


def register(client, **overrides):
    return client.post("/api/v1/auth/register", json={**USER, **overrides})


def login(client, email=USER["email"], password=USER["password"]):
    return client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_register_creates_customer(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == USER["email"]
    assert body["role"] == "customer"
    assert "password" not in body and "hashed_password" not in body


def test_register_cannot_choose_role(client):
    response = register(client, role="admin")
    assert response.status_code == 201
    assert response.json()["role"] == "customer"


def test_register_duplicate_email(client):
    register(client)
    assert register(client, email="ADA@shop.dev").status_code == 409


def test_register_validates_input(client):
    assert register(client, password="short").status_code == 422
    assert register(client, email="not-an-email").status_code == 422


def test_login_success_and_me(client):
    register(client)
    response = login(client)
    assert response.status_code == 200
    tokens = response.json()
    assert tokens["token_type"] == "bearer"

    me = client.get("/api/v1/users/me", headers=auth_header(tokens["access_token"]))
    assert me.status_code == 200
    assert me.json()["email"] == USER["email"]


def test_login_wrong_password(client):
    register(client)
    assert login(client, password="wrong-password").status_code == 401


def test_login_unknown_user(client):
    assert login(client, email="ghost@shop.dev").status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/users/me").status_code == 401
    bad = client.get("/api/v1/users/me", headers=auth_header("garbage"))
    assert bad.status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client):
    register(client)
    tokens = login(client).json()
    response = client.get(
        "/api/v1/users/me", headers=auth_header(tokens["refresh_token"])
    )
    assert response.status_code == 401


def test_refresh_rotates_tokens(client):
    register(client)
    first = login(client).json()

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]

    me = client.get("/api/v1/users/me", headers=auth_header(second["access_token"]))
    assert me.status_code == 200


def test_reusing_a_refresh_token_revokes_the_family(client):
    register(client)
    first = login(client).json()
    second = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).json()

    # Replaying the old token fails...
    replay = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert replay.status_code == 401

    # ...and the newer token is revoked as a precaution.
    newer = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}
    )
    assert newer.status_code == 401


def test_logout_revokes_refresh_token(client):
    register(client)
    tokens = login(client).json()

    out = client.post(
        "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert out.status_code == 204

    again = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert again.status_code == 401


def test_list_users_forbidden_for_customer(client):
    register(client)
    token = login(client).json()["access_token"]
    response = client.get("/api/v1/users", headers=auth_header(token))
    assert response.status_code == 403


def test_list_users_allowed_for_admin(client, admin_user):
    register(client)
    token = login(client, email="admin@shop.dev", password="admin-password").json()[
        "access_token"
    ]
    response = client.get("/api/v1/users", headers=auth_header(token))
    assert response.status_code == 200
    assert {u["email"] for u in response.json()} == {"admin@shop.dev", USER["email"]}