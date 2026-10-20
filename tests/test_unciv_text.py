import pytest

from l10n_checker.unciv_text import RenderingError, TranslationTable


@pytest.fixture
def table():
    return TranslationTable.parse(
        "# ignored\n"
        "Archery = Bogenschießen\nMining = Bergbau\n"
        "Research [technology] = [technology] erforschen\n"
        "[one] then [two] = [two], dann [one]\n"
        "Units enabled = Freigeschaltete Einheiten\n"
        "Food = Nahrung\nin all cities = in allen Städten\n"
        "[amount]% [stat] [filter] = [amount]% [stat] [filter]\n"
        "Empty = \nMultiline = Erste\\nZweite\nEquals = x = y\n"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mining", "Bergbau"),
        ("Empty", "Empty"),
        ("Unknown", "Unknown"),
        ("Research [Archery]", "Bogenschießen erforschen"),
        ("[Mining] then [Archery]", "Bogenschießen, dann Bergbau"),
        ("[Mining] then [Mining]", "Bergbau, dann Bergbau"),
        ("Research [{Mining}]", "Bergbau erforschen"),
        ("{Research [Archery]}!", "Bogenschießen erforschen!"),
        ("{Units enabled}:", "Freigeschaltete Einheiten:"),
        ("{Mining} / {Archery}", "Bergbau / Bogenschießen"),
        ("[+10]% [Food] [in all cities]", "+10% Nahrung in allen Städten"),
        ("Unknown [Mining]", "Unknown Bergbau"),
        ("Multiline", "Erste\nZweite"),
        ("Equals", "x = y"),
    ],
)
def test_rendering(table, text, expected):
    assert table.render(text) == expected


def test_nested_square_parameters():
    table = TranslationTable.parse(
        "Research [tech] = [tech] erforschen\n"
        "The city of [name] = Die Stadt [name]\nYork = York\n"
    )
    assert table.render("Research [The city of [York]]") == "Die Stadt York erforschen"


@pytest.mark.parametrize(
    "text",
    ["Mining <when [enabled]>", "Bad [Mining", "Bad {Mining", "Bad ] [Mining]"],
)
def test_unsupported_rendering_is_explicit(table, text):
    with pytest.raises(RenderingError):
        table.render(text)


def test_invalid_translation_parameter_is_explicit():
    table = TranslationTable.parse("Research [tech] = [wrong] erforschen\n")
    with pytest.raises(RenderingError, match="Unknown translated placeholder"):
        table.render("Research [Mining]")


def test_source_trace_keeps_original_parameter_names_and_lines(table):
    table.render("Research [Archery]")
    entries = table.source_entries()
    assert {e["key"] for e in entries} == {"Research [technology]", "Archery"}
    assert next(e for e in entries if e["key"] == "Archery")["line"] == 2


def test_delimiter_and_empty_rules():
    table = TranslationTable.parse("NoDelimiter=x\nEmpty = \nSame = Same\n")
    assert set(table.entries) == {"Empty", "Same"}
    assert table.render("Same") == "Same"
    with pytest.raises(RenderingError, match="no entries"):
        TranslationTable.parse("# no entries\n")
