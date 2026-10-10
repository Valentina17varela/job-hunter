import asyncio

import httpx
import respx

from jobhunter.companies import (
    Company,
    discover,
    load_companies,
    read_candidates,
    save_companies,
    slug_variants,
)
from jobhunter.http import HttpClient


def test_slug_variants():
    assert slug_variants("Stripe") == ["stripe"]
    assert slug_variants("Hugging Face") == ["huggingface", "hugging-face"]
    assert slug_variants("Weights & Biases") == ["weightsandbiases", "weights-and-biases"]
    assert slug_variants("Checkout.com") == ["checkoutcom"]
    assert slug_variants("!!!") == []


def test_read_candidates_ignores_comments_and_blanks(tmp_path):
    path = tmp_path / "c.txt"
    path.write_text("# header\nStripe\n\n  Linear  \n")
    assert read_candidates(path) == ["Stripe", "Linear"]
    assert read_candidates(tmp_path / "missing.txt") == []


def test_save_and_load_roundtrip_sorted(tmp_path):
    path = tmp_path / "companies.yaml"
    save_companies(
        path,
        [Company(name="Zed", ats="lever", slug="zed"), Company(name="Acme", ats="ashby", slug="a")],
    )
    loaded = load_companies(path)
    assert [c.name for c in loaded] == ["Acme", "Zed"]
    assert load_companies(tmp_path / "missing.yaml") == []


@respx.mock
def test_discover_finds_boards_and_skips_known(tmp_path):
    respx.get("https://boards-api.greenhouse.io/v1/boards/stripe/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [{"id": 1}]})
    )
    respx.get("https://api.lever.co/v0/postings/linear").mock(
        return_value=httpx.Response(200, json=[{"id": "x"}])
    )
    # empty board (exists but no jobs) must not count
    respx.get("https://api.ashbyhq.com/posting-api/job-board/emptyco").mock(
        return_value=httpx.Response(200, json={"jobs": []})
    )
    respx.route(host__regex=r".*").mock(return_value=httpx.Response(404))

    async def go():
        async with HttpClient(backoff=0) as http:
            return await discover(
                http,
                ["Stripe", "Linear", "EmptyCo", "Nope Inc", "Known"],
                [Company(name="Known", ats="greenhouse", slug="known")],
            )

    new, missing = asyncio.run(go())
    assert {(c.name, c.ats, c.slug) for c in new} == {
        ("Stripe", "greenhouse", "stripe"),
        ("Linear", "lever", "linear"),
    }
    assert set(missing) == {"EmptyCo", "Nope Inc"}
