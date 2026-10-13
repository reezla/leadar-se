import httpx

from lead_finder.config import Settings
from lead_finder.providers.serper_search import BATCH_LIMIT, SerperSearchError, find_websites


class FakeResponse:
    def __init__(self, status: int, payload: object) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> object:
        return self._payload


class FakeClient:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.bodies: list[object] = []

    def post(self, url: str, *, json: object, headers: dict[str, str]) -> FakeResponse:
        self.bodies.append(json)
        assert headers["X-API-KEY"] == "test-key"
        assert url == "https://google.serper.dev/search"
        return FakeResponse(200, self.payload)


def _settings() -> Settings:
    return Settings(serper_api_key="test-key")


def test_mini_batch_keeps_one_website_per_company() -> None:
    client = FakeClient(
        [
            {"organic": [{"link": "https://toofab.se/"}]},
            {
                "organic": [
                    {"link": "https://www.allabolag.se/foretag/trafikia"},
                    {"link": "https://trafikia.se/"},
                ]
            },
            {"knowledgeGraph": {"website": "https://treeline.se/"}, "organic": []},
        ]
    )
    found = find_websites(
        ["Toofab AB", "Trafikia AB", "Treeline Consulting AB"],
        settings=_settings(),
        client=client,
    )
    assert found == ["https://toofab.se/", "https://trafikia.se/", "https://treeline.se/"]
    body = client.bodies[0]
    assert isinstance(body, list)
    assert [item["q"] for item in body] == [
        "Toofab AB",
        "Trafikia AB",
        "Treeline Consulting AB",
    ]
    assert body[0]["gl"] == "se"
    assert body[0]["num"] == 10


def test_mini_batch_splits_after_one_hundred_names() -> None:
    client = FakeClient([{"organic": [{"link": "https://example.se/"}]}])

    def post(url: str, *, json: object, headers: dict[str, str]) -> FakeResponse:
        client.bodies.append(json)
        assert isinstance(json, list)
        return FakeResponse(200, [{"organic": [{"link": "https://example.se/"}]} for _ in json])

    client.post = post  # type: ignore[method-assign]
    names = [f"Company {index} AB" for index in range(BATCH_LIMIT + 1)]
    found = find_websites(names, settings=_settings(), client=client)
    assert len(found) == BATCH_LIMIT + 1
    assert [len(body) for body in client.bodies] == [BATCH_LIMIT, 1]


def test_missing_key_does_not_call_serper() -> None:
    try:
        find_websites(["Toofab AB"], settings=Settings(serper_api_key=None), client=FakeClient([]))
    except SerperSearchError as error:
        assert "SERPER_API_KEY" in str(error)
    else:
        raise AssertionError("missing key was accepted")


def test_http_error_uses_serper_message() -> None:
    class Failing:
        def post(self, url: str, *, json: object, headers: dict[str, str]) -> FakeResponse:
            return FakeResponse(403, {"message": "Not enough credits."})

    try:
        find_websites(["Toofab AB"], settings=_settings(), client=Failing())
    except SerperSearchError as error:
        assert str(error) == "Not enough credits."
    else:
        raise AssertionError("http error was ignored")


def test_request_uses_httpx_when_no_client_is_passed(monkeypatch) -> None:
    calls: list[object] = []

    class DummyClient:
        def __init__(self, timeout: float) -> None:
            calls.append(timeout)

        def post(self, url: str, *, json: object, headers: dict[str, str]) -> FakeResponse:
            calls.append(json)
            return FakeResponse(200, [{"organic": [{"link": "https://toofab.se/"}]}])

        def close(self) -> None:
            calls.append("closed")

    monkeypatch.setattr(httpx, "Client", DummyClient)
    found = find_websites(["Toofab AB"], settings=_settings())
    assert found == ["https://toofab.se/"]
    assert calls[-1] == "closed"
