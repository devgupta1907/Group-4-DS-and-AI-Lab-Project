import json
import tempfile
import unittest
from pathlib import Path

from src.experimentation import PromptExperimentStore


class PromptExperimentStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = PromptExperimentStore(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_versions_render_and_capture_exact_prompt(self):
        prompt = self.store.create_version(
            name="resume_parser",
            version="v001",
            template="Resume:\n{resume_text}",
            change_summary="baseline",
            rationale="baseline comparison",
            acceptance_criteria=["valid JSON"],
        )
        loaded, rendered = self.store.render(
            "resume_parser", "v001", {"resume_text": "Python developer"}
        )
        record = self.store.record_run(
            experiment="parser_dev",
            prompt=loaded,
            rendered_prompt=rendered,
            model="test-model",
            model_parameters={"temperature": 0},
            output={"skills": ["Python"]},
            metrics={"schema_valid": True},
        )

        run_path = Path(self.temp_dir.name) / "runs" / "parser_dev.jsonl"
        saved = json.loads(run_path.read_text().strip())
        self.assertEqual(prompt.template_sha256, loaded.template_sha256)
        self.assertEqual("Resume:\nPython developer", saved["rendered_prompt"])
        self.assertEqual(record["run_id"], saved["run_id"])

    def test_versions_are_immutable(self):
        self.store.create_version(
            name="judge",
            version="v001",
            template="{job}",
            change_summary="baseline",
            rationale="baseline",
        )
        with self.assertRaises(FileExistsError):
            self.store.create_version(
                name="judge",
                version="v001",
                template="changed {job}",
                change_summary="overwrite",
                rationale="should fail",
            )

    def test_parent_must_exist_and_missing_variables_fail(self):
        with self.assertRaises(FileNotFoundError):
            self.store.create_version(
                name="judge",
                version="v002",
                template="{job}",
                change_summary="revision",
                rationale="fix",
                parent_version="v001",
            )

        self.store.create_version(
            name="judge",
            version="v001",
            template="{resume}\n{job}",
            change_summary="baseline",
            rationale="baseline",
        )
        with self.assertRaises(ValueError):
            self.store.render("judge", "v001", {"resume": "resume"})

    def test_revision_has_metadata_and_exact_diff(self):
        self.store.create_version(
            name="judge",
            version="v001",
            template="Rank this job:\n{job}\n",
            change_summary="baseline",
            rationale="baseline",
        )
        revision = self.store.create_version(
            name="judge",
            version="v002",
            template="Rank this job from 0 to 5:\n{job}\n",
            change_summary="Added an explicit score range",
            rationale="v001 returned inconsistent score scales",
            parent_version="v001",
        )

        difference = self.store.diff_versions("judge", "v001", "v002")
        self.assertEqual("v001", revision.parent_version)
        self.assertIn("-Rank this job:", difference)
        self.assertIn("+Rank this job from 0 to 5:", difference)


if __name__ == "__main__":
    unittest.main()
