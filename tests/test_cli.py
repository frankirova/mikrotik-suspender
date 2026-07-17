import json

from cli import __main__ as cli
from core.models import ActionKind, ApplyResult, EntryResult, PlanAction, SuspensionPlan


class FakeUC:
    error = None

    async def plan(self, router, date):
        if self.error:
            raise RuntimeError(self.error)
        return SuspensionPlan.create(
            router,
            "lab-suspensions",
            date,
            "a" * 64,
            (PlanAction(ActionKind.NOOP, "10.0.0.1", "*1", "A", "done"),),
        )

    async def apply(self, plan, router):
        return ApplyResult(
            plan.plan_id, (EntryResult("10.0.0.1", ActionKind.NOOP, True, "verified"),)
        )


def setup(monkeypatch):
    monkeypatch.setattr(cli, "get_suspension_use_cases", FakeUC)
    monkeypatch.setattr(cli.bootstrap, "run", lambda: None)


def test_json_plan_is_real_json(monkeypatch, capsys):
    setup(monkeypatch)
    assert cli.main(["plan", "--router", "lab", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["router"] == "lab"


def test_apply_requires_confirmation(monkeypatch, capsys):
    setup(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda _: "no")
    assert cli.main(["apply", "--router", "lab", "--json"]) == 4
    assert json.loads(capsys.readouterr().out) == {"status": "cancelled"}


def test_apply_json_and_exit_code(monkeypatch, capsys):
    setup(monkeypatch)
    assert cli.main(["apply", "--router", "lab", "--yes", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"] == {
        "changed": 0,
        "failed": 0,
        "noop": 1,
    }


def test_installed_entry_point_preserves_json_errors_with_implicit_argv(monkeypatch, capsys):
    setup(monkeypatch)
    FakeUC.error = "injected failure"
    monkeypatch.setattr("sys.argv", ["mikrotik-suspender", "plan", "--router", "lab", "--json"])
    try:
        assert cli.main() == 1
        assert json.loads(capsys.readouterr().err) == {"error": "injected failure"}
    finally:
        FakeUC.error = None


def test_installed_entry_point_preserves_json_for_parser_errors(monkeypatch, capsys):
    setup(monkeypatch)
    monkeypatch.setattr("sys.argv", ["mikrotik-suspender", "plan", "--json"])
    assert cli.main() == 2
    assert "error" in json.loads(capsys.readouterr().err)
