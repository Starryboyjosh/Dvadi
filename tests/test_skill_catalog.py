import tempfile
import unittest
from unittest.mock import patch
from skill_catalog import _parse_selection, _remote_select, catalog_for, search
from pathlib import Path


def write_skill(root, name, description):
    path = root / name
    path.mkdir(parents=True)
    skill_file = path / "SKILL.md"
    skill_file.write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n", encoding="utf-8")
    return skill_file


class SkillCatalogTests(unittest.TestCase):
    def test_catalog_cache_invalidates_when_skill_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            skills = tmp_path / "skills"
            skill_file = write_skill(skills, "alpha", "alpha workflow")
            cache = tmp_path / "cache"
            first = catalog_for(tmp_path, [skills], str(cache), True)
            self.assertEqual(first[0]["description"], "alpha workflow")

            skill_file.write_text("---\nname: alpha\ndescription: changed workflow\n---\n", encoding="utf-8")
            second = catalog_for(tmp_path, [skills], str(cache), True)
            self.assertEqual(second[0]["description"], "changed workflow")

    def test_search_prefers_matching_skill_name(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            skills = tmp_path / "skills"
            write_skill(skills, "pdf", "create and inspect PDF files")
            write_skill(skills, "frontend", "build browser interfaces")
            entries = catalog_for(tmp_path, [skills], None, False)
            self.assertEqual(search(entries, "PDF report", 1)[0]["name"], "pdf")

    def test_provider_response_is_validated_against_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            skills = tmp_path / "skills"
            write_skill(skills, "pdf", "create PDF files")
            entries = catalog_for(tmp_path, [skills], None, False)
            selected = _parse_selection('{"skills":["pdf", "not-installed"]}', entries, 3, "ollama")
            self.assertEqual([item["name"] for item in selected], ["pdf"])

    def test_ollama_and_llamacpp_provider_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            skills = tmp_path / "skills"
            write_skill(skills, "pdf", "create PDF files")
            entries = catalog_for(tmp_path, [skills], None, False)
            with patch("skill_catalog._http_json", return_value={"message": {"content": '{"skills":["pdf"]}'}}) as request:
                self.assertEqual(_remote_select(entries, "make a PDF", 2, "ollama", None, "qwen2.5:3b")[0]["name"], "pdf")
                self.assertEqual(request.call_args.args[0], "http://127.0.0.1:11434/api/chat")
            with patch("skill_catalog._http_json", return_value={"choices": [{"message": {"content": '{"skills":["pdf"]}'}}]}) as request:
                self.assertEqual(_remote_select(entries, "make a PDF", 2, "llamacpp", None, "local-model")[0]["name"], "pdf")
                self.assertEqual(request.call_args.args[0], "http://127.0.0.1:8080/v1/chat/completions")


if __name__ == "__main__":
    unittest.main()
