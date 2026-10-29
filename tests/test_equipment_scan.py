import json
import subprocess
from types import SimpleNamespace
import pytest
from app.equipment_scan import scan_equipment
from app.knife_round import detect_knife_rounds


@pytest.fixture
def scanner(tmp_path,monkeypatch):
    from app import equipment_scan
    monkeypatch.setattr(equipment_scan,"ROOT",tmp_path)
    (tmp_path/"bin").mkdir()
    name="weapon-scan.exe" if equipment_scan.os.name=="nt" else "weapon-scan"
    (tmp_path/"bin"/name).touch()
    return dict(number=1,start=10,end=200,decision_tick=100)


def test_missing_scanner_is_unknown(tmp_path,monkeypatch):
    monkeypatch.setattr("app.equipment_scan.ROOT",tmp_path)
    assert scan_equipment("none.dem",dict(number=1,start=1,end=10))["status"]=="unknown"


def test_verified_scanner_interval_and_no_shell(scanner,monkeypatch):
    def run(args,**kwargs):
        assert args[-4:]==["-start","10","-end","100"]
        assert kwargs.get("shell",False) is False and kwargs["timeout"]==90
        return SimpleNamespace(stdout=json.dumps(dict(method="equipment-v1",status="knife",checked_frames=50)))
    monkeypatch.setattr("app.equipment_scan.subprocess.run",run)
    result=scan_equipment("a demo.dem",scanner)
    assert result["round"]==1 and result["end"]==100
    assert detect_knife_rounds(dict(rounds=[scanner,dict(number=2,start=201,end=300)],knife_scan=result))==[1]


@pytest.mark.parametrize("failure", ["timeout","invalid_json","invalid_status","crash","invalid_shape"])
def test_failures_never_hide_a_round(scanner,monkeypatch,failure):
    def run(*args,**kwargs):
        if failure=="timeout": raise subprocess.TimeoutExpired("scan",90)
        if failure=="crash": raise subprocess.CalledProcessError(1,"scan")
        return SimpleNamespace(stdout={"invalid_json":"garbage", "invalid_status":'{"status":"yes"}', "invalid_shape":"[]"}[failure])
    monkeypatch.setattr("app.equipment_scan.subprocess.run",run)
    assert scan_equipment("none.dem",scanner)["status"]=="unknown"
