"""Player profile parsers against vlr.gg pages recorded on 2026-11-19 (aspas 8480, TenZ 9) and 2026-11-25 (pndomnia 2363)."""
from pathlib import Path

import pytest

from api.scrapers.players import _parse_event_placements, _parse_teams
from utils.html_parsers import parse_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def aspas():
    return parse_html((FIXTURES / "player_8480_aspas.html").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tenz():
    return parse_html((FIXTURES / "player_9_tenz.html").read_text(encoding="utf-8"))


def test_team_name_and_period_stay_apart_when_the_card_has_an_inactive_row(aspas):
    """The italic «Inactive from …» row used to be read as the period, gluing the real one onto the name."""
    current, past = _parse_teams(aspas)
    mibr = past[1]
    assert mibr["name"] == "MIBRNovember 2024 – November 2026"  # old field, unchanged until the web stops reading it
    assert mibr["team_name"] == "MIBR"
    assert mibr["period"] == "November 2024 – November 2026"
    assert current["team_name"] == "FUT Esports"
    assert current["period"] == "joined in November 2026"


def test_every_past_team_has_a_clean_name_and_period(aspas):
    _, past = _parse_teams(aspas)
    assert [t["team_name"] for t in past] == [
        "Brazil", "MIBR", "LEVIATÁN", "LOUD", "Pancada e Amigos", "SLICK", "favela aimers",
    ]
    assert past[5]["period"] == "March 2021 – August 2021"
    assert past[6]["period"] == "left in February 2021"


def test_stage_place_is_the_numeric_range(aspas):
    placements = _parse_event_placements(aspas)
    assert placements[0]["stage_place"] == [5, 6]  # «Playoffs – 5th–6th»
    assert placements[4]["stage_place"] == [4, 4]  # «Main Event – 4th»


def test_stage_team_is_the_first_row_team_only(aspas):
    """Two series rows used to collapse into one string: «MIBRGroup Stage 5th 6thMIBR»."""
    placements = _parse_event_placements(aspas)
    assert placements[0]["stage_team"] == "MIBR"
    shanghai = next(p for p in placements if p["event"] == "Champions Tour 2024: Masters Shanghai")
    assert shanghai["stage_team"] == "FunPlus Phoenix"


def test_stage_prize_ignores_a_dollar_amount_in_the_event_name(tenz):
    """«Abe's $100,000 Valorant Invitational»: the first `$` in the text is the event name, not the prize."""
    first = _parse_event_placements(tenz)[0]
    assert first["prize"] == "$100,000"  # old field, unchanged
    assert first["stage_prize"] == "$6,000"
    assert first["stage_team"] == "Team TenZ"
    assert first["stage_place"] == [1, 1]


def test_stage_prize_is_empty_without_a_prize(aspas):
    placements = _parse_event_placements(aspas)
    assert placements[3]["stage_prize"] == ""  # VCT 2026: Americas Stage 1 has no bold prize


def test_period_skips_the_role_row_of_a_staff_card():
    """A coach card puts the role tag («head coach») in the first light row, before the period."""
    coach = parse_html((FIXTURES / "player_25616_coach.html").read_text(encoding="utf-8"))
    current, past = _parse_teams(coach)
    assert current["team_name"] == "Bpips prime"
    assert current["period"] == ""
    assert past[0]["team_name"] == "FULL SENSE SISU"
    assert past[0]["period"] == "joined in August 2026"


def test_a_card_under_past_teams_is_never_current_even_without_a_dash():
    """«left in November 2020» has no dash; with no «Current Teams» heading the player has no current team."""
    page = parse_html((FIXTURES / "player_2363_pndomnia.html").read_text(encoding="utf-8"))
    current, past = _parse_teams(page)
    assert current["team_name"] == ""
    assert [(t["team_name"], t["period"]) for t in past] == [("Paper Rex", "left in November 2020")]
