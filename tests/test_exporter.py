from pathlib import Path

import pytest

from xactflow.exporter import Exporter, discover_exporters


def test_exporter_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Exporter()


def test_concrete_exporter_subclass_can_be_instantiated_and_called():
    class FakeExporter(Exporter):
        name = "fake"

        def __init__(self):
            self.calls = []

        def export(self, subject, output_dir, **options):
            self.calls.append((subject, output_dir, options))

    exporter = FakeExporter()
    exporter.export(subject=None, output_dir=Path("/tmp/out"), foo="bar")
    assert exporter.calls == [(None, Path("/tmp/out"), {"foo": "bar"})]


def test_export_accepts_any_kind_of_subject_not_only_an_linked_design():
    # subject is deliberately untyped: an exporter may receive a LinkedDesign, a bare
    # ipxact.Component/Design an Importer just produced, or anything else it chooses to support.
    class FakeExporter(Exporter):
        name = "fake"

        def __init__(self):
            self.calls = []

        def export(self, subject, output_dir, **options):
            self.calls.append(subject)

    exporter = FakeExporter()
    bare_component = object()  # stands in for a bare ipxact.Component here
    exporter.export(bare_component, Path("/tmp/out"))
    assert exporter.calls == [bare_component]


class _FakeExporter(Exporter):
    name = "fake"

    def export(self, subject, output_dir, **options):
        pass


class _NotAnExporter:
    pass


class _FakeEntryPoint:
    def __init__(self, name, target):
        self.name = name
        self._target = target

    def load(self):
        return self._target


def test_discover_exporters_returns_registered_subclasses(monkeypatch):
    def fake_entry_points_for_group(group):
        assert group == "xactflow.exporters"
        return [_FakeEntryPoint("fake", _FakeExporter)]

    monkeypatch.setattr("xactflow.exporter._entry_points_for_group", fake_entry_points_for_group)

    exporters = discover_exporters()

    assert exporters == {"fake": _FakeExporter}


def test_discover_exporters_rejects_entry_point_that_is_not_an_exporter(monkeypatch):
    def fake_entry_points_for_group(group):
        return [_FakeEntryPoint("bad", _NotAnExporter)]

    monkeypatch.setattr("xactflow.exporter._entry_points_for_group", fake_entry_points_for_group)

    with pytest.raises(TypeError):
        discover_exporters()


def test_discover_exporters_returns_empty_dict_when_none_installed(monkeypatch):
    monkeypatch.setattr("xactflow.exporter._entry_points_for_group", lambda group: [])

    assert discover_exporters() == {}


@pytest.mark.parametrize("error", [ImportError("missing dependency"), RuntimeError("broken plugin")])
def test_discover_exporters_skips_failed_load_and_keeps_healthy_plugins(monkeypatch, capsys, error):
    class BrokenEntryPoint:
        name = "broken"

        def load(self):
            raise error

    monkeypatch.setattr(
        "xactflow.exporter._entry_points_for_group",
        lambda group: [
            _FakeEntryPoint("before", _FakeExporter),
            BrokenEntryPoint(),
            _FakeEntryPoint("after", _FakeExporter),
        ],
    )

    assert discover_exporters() == {"before": _FakeExporter, "after": _FakeExporter}
    warning = capsys.readouterr().err
    assert "warning:" in warning
    assert "broken" in warning
    assert "xactflow.exporters" in warning
    assert str(error) in warning
