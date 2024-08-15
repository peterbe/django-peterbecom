import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_feature_flag(client):
    url = reverse("publicapi:lyrics_feature_flag")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    # Because there's no IP address here
    assert not data["enabled"]

    # Pretend to be from the US
    x_forwarded_for = "US.US.US.US, 68.70.197.65"
    response = client.get(url, headers={"X-Forwarded-For": x_forwarded_for})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"]
