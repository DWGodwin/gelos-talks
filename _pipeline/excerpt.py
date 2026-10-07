"""Cut lines out of a YAML file by key path, for config panels on slides.

An excerpt keeps the file's own text and indentation, so what a slide shows is
what the config says. Three things are changed to make it fit: full-line
comments and blank lines are dropped, trailing comments are dropped unless
asked for, and a block list of scalars can be reflowed into the equivalent
flow list (`key: [a, b, c]`). When only some keys of a list item are shown, the
item's dash moves to the first of them.

Rows are dicts, in file order:
  {"t": text, "c": trailing comment, "ids": [...], "sign": "+" or "-"}
  {"head": file name, "label": ..., "color": ...}   starts a file's rows, in
                  an excerpt of several files (see Sync.diff in sync.py)
  {"gap": True}   lines of the file were left out here (not marked between a
                  key and the first line shown under it, or within one
                  selection)
`ids` tags the rows of one selection: the region names of a {{< config >}}
panel, or the option ids of a pipeline diagram.
"""

import yaml

# Reflowed lists wrap at this many characters
FLOW_WIDTH = 72


def split_comment(line):
    """(text, trailing comment or None); a # inside quotes is not a comment."""
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip(), line[i:]
    return line.rstrip(), None


def scalar(node):
    """A scalar as it would be written in a flow list."""
    return f"{node.style}{node.value}{node.style}" if node.style in ('"', "'") else node.value


class Excerpt:
    def __init__(self, path, comments=False):
        self.path = path
        self.comments = comments
        self.text = path.read_text().splitlines()
        self.root = yaml.compose("\n".join(self.text))
        self.rows = {}  # line number -> row
        self.used = set()  # lines a selection covers, shown or not

    def find(self, keys):
        """(key node, value node, key nodes of the mappings above) at a path of
        mapping keys and list indexes; None if the path doesn't exist."""
        key, node, above = None, self.root, []
        for k in keys:
            if key is not None:
                above.append(key)
            if isinstance(node, yaml.MappingNode):
                hit = next(((kn, vn) for kn, vn in node.value if kn.value == str(k)), None)
                if hit is None:
                    return None
                key, node = hit
            elif isinstance(node, yaml.SequenceNode) and isinstance(k, int) and k < len(node.value):
                key, node = None, node.value[k]
            else:
                return None
        return key, node, above

    def span(self, key, node):
        """First and last line of a key and its value."""
        first = (key or node).start_mark.line
        last = node.end_mark.line
        # A block's end mark sits at the start of whatever follows it
        if last > first and not self.text[last][: node.end_mark.column].strip():
            last -= 1
        while last > first and self.skipped(last):
            last -= 1
        return first, last

    def skipped(self, n):
        """Blank and full-line comment lines are never shown."""
        return not self.text[n].strip() or self.text[n].lstrip().startswith("#")

    def put(self, n, text, ids, sign):
        t, c = split_comment(text)
        row = {"t": t}
        if c and self.comments:
            row["c"] = c
        if ids:
            row["ids"] = list(ids)
        if sign:
            row["sign"] = sign
        self.rows[n] = row

    def add(self, keys, ids=(), flow=False, sign=None):
        """Show the key at a path and everything under it, tagged with `ids`,
        and the keys above it as untagged context. Returns False if the config
        has no such path."""
        hit = self.find(keys)
        if hit is None:
            return False
        key, node, above = hit
        for a in above:
            n = a.start_mark.line
            if n not in self.rows:
                self.put(n, self.text[n], (), None)
        self.emit(key, node, ids, flow, sign)
        return True

    def cut(self, keys, sign=None):
        """The rows of the key at a path alone, lists reflowed, without adding
        them to the excerpt; [] if the config has no such path."""
        hit = self.find(keys)
        if hit is None:
            return []
        kept, self.rows = self.rows, {}
        self.emit(hit[0], hit[1], (), True, sign)
        rows, self.rows = [self.rows[n] for n in sorted(self.rows)], kept
        return rows

    def key_line(self, keys):
        """The line that holds the key at a path, as an untagged row."""
        hit = self.find(keys)
        return hit and {"t": split_comment(self.text[hit[0].start_mark.line])[0]}

    def add_item(self, keys, fields, sign=None):
        """Show some keys of the mapping at a path, usually a list item:
        `fields` maps each key to its ids. Returns False if the path doesn't
        lead to a mapping."""
        hit = self.find(keys)
        if hit is None or not isinstance(hit[1], yaml.MappingNode):
            return False
        node, dashed = hit[1], False
        for kn, _ in node.value:
            if kn.value not in fields:
                continue
            self.add([*keys, kn.value], fields[kn.value], sign=sign)
            n = kn.start_mark.line
            lead = self.text[node.start_mark.line][: node.start_mark.column]
            if not dashed and n != node.start_mark.line and lead.strip() == "-":
                self.rows[n]["t"] = lead + self.rows[n]["t"].lstrip()
            dashed = True
        return dashed

    def emit(self, key, node, ids, flow, sign):
        first, last = self.span(key, node)
        self.used.update(range(first, last + 1))
        if flow and key is not None and first < last:
            if isinstance(node, yaml.MappingNode):
                self.put(first, self.text[first], ids, sign)
                for kn, vn in node.value:
                    self.emit(kn, vn, ids, flow, sign)
                return
            if isinstance(node, yaml.SequenceNode) and all(
                isinstance(v, yaml.ScalarNode) for v in node.value
            ):
                head = self.text[first][: key.end_mark.column] + ": ["
                lines, line = [], head
                for i, v in enumerate(node.value):
                    item = scalar(v) + ("," if i < len(node.value) - 1 else "]")
                    if len(line) + len(item) + 1 > FLOW_WIDTH and line.strip() != head.strip():
                        lines.append(line.rstrip())
                        line = " " * len(head)
                    line += item + " "
                lines.append(line.rstrip())
                # A block list has a line per item, so the flow lines fit in it
                for i, text in enumerate(lines):
                    self.put(first + i, text, ids, sign)
                return
        for n in range(first, last + 1):
            if not self.skipped(n):
                self.put(n, self.text[n], ids, sign)

    def result(self):
        """Rows in file order, with a gap row wherever lines were left out."""
        def indent(row):
            return len(row["t"]) - len(row["t"].lstrip())

        out, prev = [], None
        for n in sorted(self.rows):
            row = self.rows[n]
            if prev is not None:
                above = self.rows[prev]
                descent = "ids" not in above and indent(row) > indent(above)
                same = "ids" in row and row.get("ids") == above.get("ids")
                left_out = any(
                    not self.skipped(i) and i not in self.used for i in range(prev + 1, n)
                )
                if left_out and not descent and not same:
                    out.append({"gap": True})
            out.append(row)
            prev = n
        return out
