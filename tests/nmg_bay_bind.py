"""Bind authored NMG bay source only after its sole writer is terminal."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from tools import v03_inline_delivery_adapter as adapter
from test_v03_nmg_school_adapter import bind_sources

PATH = ROOT / "data/content/v03/countries/nmg.json"
SLUG = "v03_nmg_bay_ports"


def bind_text(text):
    catalog = json.loads(text)
    matches = [arc for arc in catalog["arcs"] if arc.get("slug") == SLUG]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one bay arc, got {len(matches)}")
    arc = matches[0]
    if "inline_delivery_adapter" in arc:
        raise ValueError("existing bay metadata: refuse overwrite")
    bound = copy.deepcopy(arc)
    bind_sources(bound)
    for index, phase in enumerate(bound["inline_delivery_adapter"]["live_phases"], 1):
        phase["live_witness"] = f"ywc_v03_nmg_inline_live_bay_{index}"
    prospective = copy.deepcopy(catalog)
    target = next(a for a in prospective["arcs"] if a["slug"] == SLUG)
    target["inline_delivery_adapter"] = bound["inline_delivery_adapter"]
    adapter.validate_inline_catalog(prospective)
    decoder = json.JSONDecoder()
    slug_at = text.find('"' + SLUG + '"')
    spans = []
    for index in range(slug_at - 1, -1, -1):
        if text[index] != "{":
            continue
        try:
            obj, end = decoder.raw_decode(text, index)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("slug") == SLUG and obj == arc:
            spans.append((index, end))
    if len(spans) != 1:
        raise ValueError(f"expected one exact raw arc span, got {len(spans)}")
    _, end = spans[0]
    closing = end - 1
    if text[closing] != "}":
        raise ValueError("arc closing delimiter mismatch")
    line_start = text.rfind("\n", 0, closing) + 1
    indent = text[line_start:closing]
    if indent.strip():
        raise ValueError("arc closing brace is not on its own line")
    newline = "\r\n" if "\r\n" in text else "\n"
    metadata = json.dumps(bound["inline_delivery_adapter"], ensure_ascii=False, indent=2)
    field_indent = indent + "  "
    metadata = metadata.replace("\n", newline + field_indent)
    insertion = "," + newline + field_indent + '"inline_delivery_adapter": ' + metadata + newline + indent
    prefix_end = line_start
    while prefix_end > 0 and text[prefix_end - 1] in "\r\n":
        prefix_end -= 1
    result = text[:prefix_end] + insertion + text[closing:]
    if json.loads(result) != prospective:
        raise ValueError("bound catalog semantic verification failed")
    return result


def main():
    raw = PATH.read_bytes()
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    original = raw[len(bom):].decode("utf-8")
    result = bind_text(original)
    # Construct a complete sibling first so an interrupted write cannot leave
    # a truncated catalog. The writer must be terminal before invoking this;
    # the second comparison detects changes while validation was running.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=PATH.parent, prefix=".nmg-bay-bind-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(bom + result.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        if PATH.read_bytes() != raw:
            raise RuntimeError("catalog changed during binding; no write performed")
        os.replace(temporary, PATH)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print("NMG bay: bound exact two phases and eight sender branches; foreign reply is outside native delivery")


if __name__ == "__main__":
    main()
