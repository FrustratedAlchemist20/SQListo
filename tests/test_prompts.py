"""Prompt compatibility and SQLite integration without a model or network.

The frozen payloads come from GitHub main before prompt externalization.
SQLite parsing, validation, repair decisions and execution remain real; only
inference responses are controlled by the tests.
"""

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest import mock

import sqlisto_agent as agent
import sqlisto_prompts as prompts
import xyz2db_assistant as assistant


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "prompts_github_main.json"
ORIGINAL_CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
TEMPLATES = {
    "build_router_prompt": "router.txt",
    "build_prompt": "sql_generation.txt",
    "build_repair_prompt": "sql_repair.txt",
}


def consumer_builder(name):
    module = agent if name == "build_router_prompt" else assistant
    return getattr(module, name)


class PromptCompatibilityTests(unittest.TestCase):
    def assert_original_payload(self, case):
        payload = consumer_builder(case["builder"])(**case["arguments"])
        self.assertEqual(len(payload), case["characters"])
        self.assertEqual(
            hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            case["sha256"],
        )

    def test_all_payloads_match_github_main_including_router(self):
        # Cases include Unicode, empty knowledge/catalogues, JSON braces,
        # backslashes and dollar placeholders inside the supplied context.
        for index, case in enumerate(ORIGINAL_CASES):
            with self.subTest(builder=case["builder"], case=index):
                self.assert_original_payload(case)

    def test_templates_are_found_outside_the_project_directory(self):
        previous_directory = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                for case in ORIGINAL_CASES:
                    with self.subTest(builder=case["builder"]):
                        self.assert_original_payload(case)
            finally:
                os.chdir(previous_directory)

    def test_template_edits_are_read_on_the_next_call(self):
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "prompts"
            shutil.copytree(prompts.PROMPTS_DIR, copied)
            with mock.patch.object(prompts, "PROMPTS_DIR", copied):
                for builder_name, filename in TEMPLATES.items():
                    case = next(c for c in ORIGINAL_CASES if c["builder"] == builder_name)
                    builder = consumer_builder(builder_name)
                    with self.subTest(template=filename):
                        before = builder(**case["arguments"])
                        path = copied / filename
                        addition = "\nAdditional test instruction.\n"
                        path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")
                        self.assertEqual(builder(**case["arguments"]), before + addition)


class PromptPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.db_path = str(Path(self.temporary.name) / "example.db")
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "CREATE TABLE trajectories (traj_uid TEXT PRIMARY KEY, molecule TEXT)"
            )
            connection.executemany(
                "INSERT INTO trajectories VALUES (?, ?)",
                [("t1", "Molécula A"), ("t2", "Molécula A"), ("t3", "Molécula B")],
            )
            connection.commit()
        finally:
            # Close the fixture before using the existing immutable reader.
            connection.close()
        self.schema = assistant.get_sqlite_schema(self.db_path)
        self.question = "¿Cuántas trayectorias hay? ${schema} {literal}"
        self.knowledge = "Each row in trajectories represents one trajectory."
        self.valid_sql = "SELECT COUNT(*) AS total FROM trajectories;"
        self.invalid_sql = "SELECT absent_column FROM trajectories;"
        self.rejected_sql = "SELECT absent_column FROM trajectories\nLIMIT 25;"

    def generate_sql(self, **overrides):
        arguments = {
            "db_path": self.db_path,
            "question": self.question,
            "schema": self.schema,
            "knowledge": self.knowledge,
            "model_path": "unused-model.gguf",
            "llama_cli": "unused-llama-cli",
            "n_tokens": 64,
            "timeout_seconds": 30,
            "max_rows": 25,
            "max_repairs": 1,
        }
        arguments.update(overrides)
        return assistant.generate_valid_sql(**arguments)

    def generate_plan(self):
        return agent.generate_agent_plan(
            question=self.question,
            tools_manual="unused manual",
            catalog={"molecules": ["Molécula A", "Molécula B"]},
            model_path="unused-model.gguf",
            llama_cli="unused-llama-cli",
            router_tokens=80,
            router_timeout=40,
        )

    def generation_prompt(self):
        return assistant.build_prompt(self.schema, self.question, self.knowledge)

    def repair_prompt(self):
        return assistant.build_repair_prompt(
            self.schema,
            self.question,
            self.knowledge,
            self.rejected_sql,
            "no such column: absent_column",
        )

    def assert_total(self, sql):
        result = assistant.execute_sql(self.db_path, sql)
        self.assertEqual(list(result.columns), ["total"])
        self.assertEqual(result["total"].tolist(), [3])

    def test_router_passes_complete_prompt_and_preserves_backend_arguments(self):
        with mock.patch.object(agent, "run_llama_backend", return_value='{"action":"database_summary"}') as backend:
            plan = self.generate_plan()
        self.assertEqual(plan, {"action": "database_summary"})
        backend.assert_called_once_with(
            model_path="unused-model.gguf",
            prompt=agent.build_router_prompt(
                self.question, "unused manual", {"molecules": ["Molécula A", "Molécula B"]}
            ),
            llama_cli="unused-llama-cli",
            n_tokens=80,
            timeout_seconds=40,
        )

    def test_sql_generation_is_validated_and_executed_by_sqlite(self):
        with mock.patch.object(assistant, "run_llama_cli", return_value=self.valid_sql) as backend:
            sql, repairs = self.generate_sql()
        self.assertEqual(repairs, 0)
        backend.assert_called_once_with(
            model_path="unused-model.gguf",
            prompt=self.generation_prompt(),
            llama_cli="unused-llama-cli",
            n_tokens=64,
            timeout_seconds=30,
        )
        self.assert_total(sql)

    def test_real_sqlite_error_is_inserted_into_the_repair_prompt(self):
        with mock.patch.object(
            assistant, "run_llama_cli", side_effect=[self.invalid_sql, self.valid_sql]
        ) as backend:
            sql, repairs = self.generate_sql()
        self.assertEqual(repairs, 1)
        self.assertEqual(backend.call_count, 2)
        self.assertEqual(backend.call_args_list[0].kwargs["prompt"], self.generation_prompt())
        self.assertEqual(backend.call_args_list[1].kwargs["prompt"], self.repair_prompt())
        self.assert_total(sql)

    def test_failed_repair_raises_the_real_sqlite_error_at_the_existing_limit(self):
        with mock.patch.object(assistant, "run_llama_cli", return_value=self.invalid_sql) as backend:
            with self.assertRaises(assistant.SQLiteValidationError) as raised:
                self.generate_sql(max_repairs=1)
        self.assertEqual(backend.call_count, 2)
        self.assertEqual(raised.exception.sqlite_error, "no such column: absent_column")
        self.assertEqual(raised.exception.sql, self.rejected_sql)
        self.assert_total(self.valid_sql)

    def test_missing_or_invalid_initial_templates_fail_before_inference(self):
        for filename, invoke in (
            ("router.txt", self.generate_plan),
            ("sql_generation.txt", self.generate_sql),
        ):
            for problem in ("missing file", "missing field", "unknown field", "malformed field"):
                with self.subTest(template=filename, problem=problem):
                    with tempfile.TemporaryDirectory() as directory:
                        copied = Path(directory) / "prompts"
                        shutil.copytree(prompts.PROMPTS_DIR, copied)
                        self.damage_template(copied / filename, problem, "question")
                        with (
                            mock.patch.object(prompts, "PROMPTS_DIR", copied),
                            mock.patch.object(agent, "run_llama_backend") as router,
                            mock.patch.object(assistant, "run_llama_cli") as sql_backend,
                        ):
                            expected_error = FileNotFoundError if problem == "missing file" else ValueError
                            with self.assertRaises(expected_error):
                                invoke()
                            router.assert_not_called()
                            sql_backend.assert_not_called()

    def test_missing_or_invalid_repair_template_prevents_a_second_inference(self):
        for problem in ("missing file", "missing field", "unknown field", "malformed field"):
            with self.subTest(problem=problem):
                with tempfile.TemporaryDirectory() as directory:
                    copied = Path(directory) / "prompts"
                    shutil.copytree(prompts.PROMPTS_DIR, copied)
                    self.damage_template(copied / "sql_repair.txt", problem, "sqlite_error")
                    with (
                        mock.patch.object(prompts, "PROMPTS_DIR", copied),
                        mock.patch.object(assistant, "run_llama_cli", return_value=self.invalid_sql) as backend,
                    ):
                        expected_error = FileNotFoundError if problem == "missing file" else ValueError
                        with self.assertRaises(expected_error):
                            self.generate_sql()
                        self.assertEqual(backend.call_count, 1)

    @staticmethod
    def damage_template(path, problem, field):
        if problem == "missing file":
            path.unlink()
            return
        text = path.read_text(encoding="utf-8")
        if problem == "missing field":
            text = text.replace("${" + field + "}", "")
        elif problem == "unknown field":
            text += "\n${unexpected_field}\n"
        else:
            text += "\n${unfinished\n"
        path.write_text(text, encoding="utf-8")

    def test_configured_server_receives_both_generation_and_sqlite_repair(self):
        responses = [self.invalid_sql, self.valid_sql]

        def reply(_request, **_kwargs):
            payload = json.dumps({"content": responses.pop(0)}).encode("utf-8")
            return io.BytesIO(payload)

        # Restore all global configuration after exercising the real backend
        # redirection. Only the HTTP boundary and health probe are simulated.
        with (
            mock.patch.object(agent, "ACTIVE_LLAMA_URL", agent.ACTIVE_LLAMA_URL),
            mock.patch.object(agent, "ACTIVE_LLAMA_FALLBACK", agent.ACTIVE_LLAMA_FALLBACK),
            mock.patch.object(assistant, "run_llama_cli", assistant.run_llama_cli),
            mock.patch.object(agent, "llama_server_healthcheck", return_value=True),
            mock.patch.object(agent, "ORIGINAL_RUN_LLAMA_CLI") as cli,
            mock.patch.object(agent.urllib.request, "urlopen", side_effect=reply) as http,
        ):
            self.assertEqual(
                agent.configure_llm_backend("http://127.0.0.1:19080/", allow_cli_fallback=False),
                "llama-server",
            )
            sql, repairs = self.generate_sql()
            cli.assert_not_called()
        self.assertEqual(repairs, 1)
        self.assertEqual(http.call_count, 2)
        for call, expected_prompt in zip(
            http.call_args_list, [self.generation_prompt(), self.repair_prompt()]
        ):
            request = call.args[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:19080/completion")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(call.kwargs["timeout"], 30)
            payload = json.loads(request.data.decode("utf-8"))
            self.assertEqual(payload["prompt"], expected_prompt)
            self.assertEqual(payload["n_predict"], 64)
        self.assert_total(sql)


if __name__ == "__main__":
    unittest.main()
