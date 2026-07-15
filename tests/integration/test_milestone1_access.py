"""Live local-Supabase checks for Milestone 1 access controls."""

import os
import uuid

import httpx
import pytest


def _required_environment() -> tuple[str, str, str]:
    values = (
        os.getenv("SUPABASE_TEST_URL"),
        os.getenv("SUPABASE_TEST_ANON_KEY"),
        os.getenv("SUPABASE_TEST_SERVICE_ROLE_KEY"),
    )
    if any(value is None for value in values):
        pytest.skip("local Supabase integration credentials are not configured")
    return values  # type: ignore[return-value]


def _headers(key: str, *, write: bool = False) -> dict[str, str]:
    profile_header = "Content-Profile" if write else "Accept-Profile"
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        profile_header: "knowledge",
    }


def test_anon_cannot_read_or_write_knowledge_tables() -> None:
    base_url, anon_key, _ = _required_environment()
    endpoint = f"{base_url.rstrip('/')}/rest/v1/embedding_models"

    with httpx.Client(timeout=5.0) as client:
        read_response = client.get(endpoint, headers=_headers(anon_key))
        write_response = client.post(
            endpoint,
            headers={**_headers(anon_key, write=True), "Prefer": "return=representation"},
            json={
                "model_key": f"anon-denied-{uuid.uuid4()}",
                "provider": "test",
                "model_name": "must-not-exist",
                "dimensions": 1024,
            },
        )

    assert read_response.status_code in {401, 403} or read_response.json() == []
    assert write_response.status_code in {401, 403}


def test_service_role_can_crud_knowledge_tables() -> None:
    base_url, _, service_key = _required_environment()
    endpoint = f"{base_url.rstrip('/')}/rest/v1/sync_runs"
    marker = str(uuid.uuid4())
    headers = {**_headers(service_key, write=True), "Prefer": "return=representation"}

    with httpx.Client(timeout=5.0) as client:
        create_response = client.post(
            endpoint,
            headers=headers,
            json={
                "status": "running",
                "sync_type": "initial",
                "details": {"integration_test": marker},
            },
        )
        assert create_response.status_code == 201
        row_id = create_response.json()[0]["id"]

        read_response = client.get(
            endpoint,
            headers=_headers(service_key),
            params={"id": f"eq.{row_id}", "select": "id,status,details"},
        )
        assert read_response.status_code == 200
        assert read_response.json()[0]["details"]["integration_test"] == marker

        update_response = client.patch(
            endpoint,
            headers=headers,
            params={"id": f"eq.{row_id}"},
            json={"status": "cancelled"},
        )
        assert update_response.status_code == 200
        assert update_response.json()[0]["status"] == "cancelled"

        delete_response = client.delete(
            endpoint,
            headers=headers,
            params={"id": f"eq.{row_id}"},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()[0]["id"] == row_id


def test_raw_storage_bucket_is_private() -> None:
    base_url, anon_key, service_key = _required_environment()
    object_path = f"milestone1/{uuid.uuid4()}.json"
    endpoint = f"{base_url.rstrip('/')}/storage/v1/object/dst-wiki-raw/{object_path}"

    with httpx.Client(timeout=5.0) as client:
        upload_response = client.post(
            endpoint,
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
            },
            content=b'{"fixture":true}',
        )
        assert upload_response.status_code == 200

        anon_response = client.get(
            endpoint,
            headers={
                "apikey": anon_key,
                "Authorization": f"Bearer {anon_key}",
            },
        )
        assert anon_response.status_code in {400, 401, 403, 404}

        delete_response = client.delete(
            endpoint,
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
        )
        assert delete_response.status_code in {200, 204}
