#!/usr/bin/env python3

"""
Ensure failures remain visible even when placeholders are written.
"""

from types import SimpleNamespace

import pytest
import numpy as np

from py4radiation.pyciao import runner

@pytest.mark.parametrize("mode", [1, 3])
@pytest.mark.parametrize("failed_indices", [(), (1,), (0, 1, 2)])

def test_execution_failure_reporting(tmp_path, monkeypatch, mode, failed_indices):
    config = SimpleNamespace(
        params = {
            "cloudyExe": "not-called",
            "coolingMapTmin": "1e3",
            "coolingMapTmax": "1e5",
            "coolingMapTpoints": "3",
            "coolingScaleFactor": "1",
            "ionFractionElements": "H"
        }, loops_cmd = []
    )

    task = {"run_index": 1, "key_name": str(tmp_path / "demo_run1"), "base_commands": [], "run_mode": mode}

    monkeypatch.setattr(runner, "WORKER_CONFIG", config)

    # Simulate success or failure at each temperature
    outcomes = iter(i in failed_indices for i in range(3))
    monkeypatch.setattr(runner, "run_subprocess", lambda *args: next(outcomes))

    # Controlled physical quantities for successful runs.
    monkeypatch.setattr(runner, "_get_physical_conditions", lambda *args: (2.0, 4.0))
    monkeypatch.setattr(runner, "_get_cooling", lambda *args: (40.0, 80.0))
    monkeypatch.setattr(runner, "_get_mmw", lambda *args: 1.25)
    monkeypatch.setattr(runner, "_get_ion_fraction", lambda *args: {"H": [-0.301, -0.301]})

    outcome = runner.execute_task(task)
    n_failed = len(failed_indices)

    assert outcome["run_index"] == 1
    assert outcome["status"] == ("failed" if n_failed else "success")
    assert (outcome["error"] is None) == (n_failed == 0)

    if n_failed:
        assert f"{n_failed} temperature" in outcome["error"]

    # Read the output written by the runner
    suffix = ".dat" if mode == 1 else "_H.dat"
    rows = np.loadtxt(str(tmp_path / "demo_run1") + suffix, comments="#", ndmin=2)

    assert rows.shape == (3, 4 if mode == 1 else 3)

    expected_temperatures = ([1e3, 1e4, 1e5] if mode == 1 else [3.0, 4.0, 5.0])

    np.testing.assert_allclose(rows[:, 0], expected_temperatures, rtol=1e-12, atol=0)

    for i, row in enumerate(rows):
        if mode == 1:
            expected = ([0.0, 0.0, 0.0] if i in failed_indices else [10.0, 20.0, 1.25])
        else:
            expected = ([-30.0, -30.0] if i in failed_indices else [-0.301, -0.301])

        np.testing.assert_allclose(row[1:], expected, rtol=1e-12, atol=0)
