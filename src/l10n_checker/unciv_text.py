"""Small source-backed subset of Unciv's TranslationFileReader/String.tr.

Supports plain text, nested [] parameters and {} sentences. Conditionals,
number localization, mods, stat serialization and icon insertion are outside
this textual renderer; callers must supply those as separate screen context.
"""

import re
from dataclasses import dataclass, field


class RenderingError(ValueError):
    pass


def groups(text: str, opening: str, closing: str) -> list[tuple[int, int, str]]:
    """Outermost balanced groups, including nested groups in their content."""
    result = []
    depth = 0
    start = 0
    for index, char in enumerate(text):
        if char == opening:
            if depth == 0:
                start = index
            depth += 1
        elif char == closing:
            depth -= 1
            if depth < 0:
                raise RenderingError(f"Unbalanced {opening}{closing}: {text}")
            if depth == 0:
                result.append((start, index + 1, text[start + 1 : index]))
    if depth:
        raise RenderingError(f"Unbalanced {opening}{closing}: {text}")
    return result


def skeleton(text: str) -> str:
    for start, end, _ in reversed(groups(text, "[", "]")):
        text = text[:start] + "[]" + text[end:]
    return text


@dataclass
class TranslationTable:
    # skeleton -> (original key, nonempty value or None, source line number)
    entries: dict[str, tuple[str, str | None, int]]
    used: set[str] = field(default_factory=set)
    lookups: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, content: str) -> "TranslationTable":
        entries = {}
        for number, line in enumerate(content.splitlines(), 1):
            if not line or line.startswith("#") or " = " not in line:
                continue
            key, value = line.split(" = ", 1)
            key, value = key.replace(r"\n", "\n"), value.replace(r"\n", "\n")
            # The upstream reader keeps only nonempty values. Keep empty keys
            # too for English provenance; render them using the same fallback.
            index = skeleton(key) if "[" in key and "<" not in key else key
            entries[index] = (key, value or None, number)
        if not entries:
            raise RenderingError("Translation file contains no entries")
        return cls(entries)

    def render(self, text: str, depth: int = 0) -> str:
        if depth > 20:
            raise RenderingError("Translation nesting exceeds 20 levels")
        if "<" in text or ">" in text:
            raise RenderingError(f"Conditional rendering is unsupported: {text}")
        groups(text, "[", "]")
        groups(text, "{", "}")
        first = min((text.find(c) for c in "[{" if c in text), default=-1)
        if first < 0:
            entry = self.entries.get(text)
            self.used.add(text)
            self.lookups.append(text)
            return entry[1] if entry and entry[1] is not None else text
        if text[first] == "{":
            parts = groups(text, "{", "}")
            for start, end, value in reversed(parts):
                text = text[:start] + self.render(value, depth + 1) + text[end:]
            return text

        params = groups(text, "[", "]")
        index = skeleton(text)
        self.used.add(index)
        self.lookups.append(index)
        entry = self.entries.get(index)
        original, translated = (entry[0], entry[1]) if entry else (text, None)
        if translated is None:
            original, translated = text, text
        names = [value for _, _, value in groups(original, "[", "]")]
        if len(names) != len(params):
            raise RenderingError(f"Placeholder arity differs: {text}")
        replacements = {
            name: self.render(value, depth + 1)
            for name, (_, _, value) in zip(names, params, strict=True)
        }
        # Substitute simultaneously so a parameter cannot rewrite another one.
        output = []
        cursor = 0
        for start, end, name in groups(translated, "[", "]"):
            if name not in replacements:
                raise RenderingError(f"Unknown translated placeholder: [{name}]")
            output.extend((translated[cursor:start], replacements[name]))
            cursor = end
        output.append(translated[cursor:])
        rendered = "".join(output)
        if re.search(r"[{}]", rendered):
            raise RenderingError(f"Unsupported mixed translated template: {translated}")
        return rendered

    def source_entries(self) -> list[dict]:
        return [
            {"key": entry[0], "value": entry[1], "line": entry[2]}
            if (entry := self.entries.get(key))
            else {"key": key, "value": None, "line": None}
            for key in sorted(self.used)
        ]
