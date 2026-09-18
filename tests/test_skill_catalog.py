import tempfile
import unittest
from skill_catalog import catalog_for, search
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


if __name__ == "__main__":
    unittest.main()
