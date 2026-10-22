"""Small, persistent outlines independent of editor HTML and title spelling."""
from difflib import SequenceMatcher
from collections import defaultdict, deque
from html.parser import HTMLParser
from uuid import uuid4

from markdown import markdown


class HeadingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings = []
        self.level = None
        self.text = []
        self.code_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("pre", "code"):
            self.code_depth += 1
        if tag in ("h1", "h2", "h3") and not self.code_depth:
            self.level = int(tag[1])
            self.text = []
        if tag == "img" and self.level:
            self.text.append(dict(attrs).get("alt", ""))

    def handle_data(self, data):
        if self.level:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3") and self.level:
            title = " ".join("".join(self.text).split())
            if title:
                self.headings.append({"level": self.level, "title": title})
            self.level = None
        if tag in ("pre", "code"):
            self.code_depth = max(0, self.code_depth - 1)


def build_outline(content, previous=None):
    parser = HeadingParser()
    parser.feed(markdown(content or "", extensions=["extra"]))
    # CKEditor's Heading 1/2 serialize as h2/h3 (Markdown ##/###).
    # Markdown h1 is also accepted as a top-level chapter.
    result = [{"level": 2 if h["level"] == 3 else 1, "title": h["title"]} for h in parser.headings]
    previous = previous or []
    key = lambda entry: (entry["level"], entry["title"])
    existing = defaultdict(deque)
    for entry in previous:
        existing[key(entry)].append(entry["id"])
    used = set()
    for entry in result:
        if existing[key(entry)]:
            entry["id"] = existing[key(entry)].popleft()
            used.add(entry["id"])
    matcher = SequenceMatcher(None, list(map(key, previous)), list(map(key, result)), autojunk=False)
    for operation, a, b, c, d in matcher.get_opcodes():
        # Equal headings survive moves nearby; one-for-one replacements retain
        # their identity when renamed. Inserted headings get their own IDs.
        if operation == "equal" or (operation == "replace" and b - a == d - c):
            for old, new in zip(previous[a:b], result[c:d]):
                if "id" not in new and old["id"] not in used:
                    new["id"] = old["id"]
                    used.add(old["id"])
    for entry in result:
        entry.setdefault("id", "wiki-" + uuid4().hex)
    return result
