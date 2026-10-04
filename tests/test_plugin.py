import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SKILLS = {
    "before-and-after", "code-structure", "evidence-driven-testing",
    "greploop", "greploop-apps", "new-feature", "unslop",
}


def manifest():
    return json.loads((ROOT / ".codex-plugin/plugin.json").read_text())


def test_manifest_identifies_skills_only_plugin():
    data = manifest()
    assert data["name"] == "devagent"
    assert data["version"] == "1.0.0"
    assert data["author"]["name"]
    assert data["description"]
    assert not {"mcpServers", "apps", "hooks"}.intersection(data)


def test_all_seven_skills_and_resources_are_inside_package():
    paths = manifest()["skills"]
    assert len(paths) == len(SKILLS)
    assert {Path(path).name for path in paths} == SKILLS
    for path in paths:
        assert path.startswith("./")
        assert ".." not in Path(path).parts
        folder = (ROOT / path).resolve()
        assert folder.is_relative_to(ROOT)
        assert (folder / "SKILL.md").is_file()
    assert (ROOT / "evidence-driven-testing/scripts/evidence.py").is_file()
    for skill in ("greploop", "greploop-apps"):
        assert (ROOT / skill / "references/graphql-queries.md").is_file()
    for skill in ("before-and-after", "greploop", "greploop-apps", "unslop"):
        assert (ROOT / skill / "LICENSE").is_file()


def test_marketplace_resolves_plugin_from_repository_root():
    catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    assert catalog["name"] == "devagent-marketplace"
    entries = catalog["plugins"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["name"] == manifest()["name"]
    assert entry["source"]["source"] == "local"
    assert entry["source"]["path"] == "./"
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] == "ON_INSTALL"
    assert entry["category"] == "Developer Tools"
    assert (ROOT / entry["source"]["path"] / ".codex-plugin/plugin.json").is_file()


def test_listing_metadata_and_icons():
    ui = manifest()["interface"]
    for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        assert ui[field]
    assert len(ui["displayName"]) <= 30
    assert len(ui["shortDescription"]) <= 30
    assert isinstance(ui["capabilities"], list)
    for field in ("logo", "composerIcon"):
        path = ui[field]
        assert path.startswith("./assets/")
        assert ".." not in Path(path).parts
        icon = ROOT / path
        assert icon.stat().st_size <= 5 * 1024 * 1024
        svg = ET.parse(icon).getroot()
        _, _, width, height = map(float, svg.attrib["viewBox"].split())
        assert width == height and width >= 48
