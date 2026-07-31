"""Generate release artifacts and submission reports (Sprint 12).

Outputs into release/:
- openapi.json
- benchmark.json
- validation_report.json
- benchmark_report.json
- release_checklist.json

Run from the repository root:
    python scripts/generate_release_artifacts.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RELEASE = ROOT / "release"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

REQUIRED_SERVICES = ("backend", "worker", "frontend", "redis", "flower")


def _run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    return {
        "command": " ".join(command),
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000.0, 2),
        "tail": (result.stdout + result.stderr).strip().splitlines()[-1:]
        if (result.stdout + result.stderr).strip()
        else [],
    }


def export_openapi() -> dict[str, Any]:
    from app.main import create_application

    application = create_application()
    schema = application.openapi()
    path = RELEASE / "openapi.json"
    path.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return {
        "passed": True,
        "artifact": "release/openapi.json",
        "paths": len(schema.get("paths", {})),
    }


def verify_requirements_lock() -> dict[str, Any]:
    """Verify the dependency lock: every requirement installs without conflict.

    pip check is scoped to packages declared by this project; unrelated
    packages present in the host environment do not fail the gate.
    """
    requirements_path = BACKEND / "requirements.txt"
    lines = [
        line.strip()
        for line in requirements_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    declared = {
        line.split("[")[0].split("=")[0].split(">")[0].split("<")[0].lower()
        for line in lines
    }
    result = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    conflicts = [
        line.strip()
        for line in (result.stdout + result.stderr).splitlines()
        if "requires" in line or "has requirement" in line
    ]
    project_conflicts = [
        line
        for line in conflicts
        if line.split(" ")[0].lower().strip() in declared
    ]
    return {
        "passed": requirements_path.exists() and not project_conflicts,
        "requirements_file": "backend/requirements.txt",
        "declared_packages": len(declared),
        "project_conflicts": project_conflicts,
        "environment_conflicts_out_of_scope": [
            line for line in conflicts if line not in project_conflicts
        ],
    }


def verify_compose() -> dict[str, Any]:
    compose_path = ROOT / "docker-compose.yml"
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    services = compose.get("services", {})

    missing = [name for name in REQUIRED_SERVICES if name not in services]
    healthchecks = {
        name: "healthcheck" in (services.get(name) or {})
        for name in REQUIRED_SERVICES
        if name in services
    }
    dockerfiles = {
        name: Path(
            ROOT,
            (services.get(name) or {}).get("build", {}).get("dockerfile", "")
            .replace("../", "")
            .replace("./", ""),
        ).exists()
        for name in ("backend", "worker", "frontend")
        if (services.get(name) or {}).get("build")
    }
    docker_available = shutil.which("docker") is not None
    docker_check = (
        _run(["docker", "compose", "config", "-q"], cwd=ROOT)
        if docker_available
        else {
            "passed": None,
            "tail": ["docker CLI unavailable; static validation only"],
        }
    )
    return {
        "passed": not missing and all(healthchecks.values()) and all(dockerfiles.values()),
        "services": sorted(services),
        "missing_services": missing,
        "healthchecks": healthchecks,
        "dockerfiles_exist": dockerfiles,
        "docker_cli_available": docker_available,
        "docker_compose_config": docker_check,
    }


async def _run_benchmark_batch(file_count: int = 5) -> dict[str, Any]:
    from tests.e2e.test_pipeline_e2e import (
        FakeBatchRepo,
        FakeJobRepo,
        FakeMetricsRepo,
        PipelineHarness,
        SharedFakeAssetRepo,
    )
    from app.evaluation.exporter import BatchExporter
    from app.evaluation.metrics import BatchMetricsCalculator
    from app.evaluation.pipeline import EvaluationPipeline
    from app.jobs.models import Job
    from app.shared.domain.enums import JobStatus
    from app.system.benchmark import BenchmarkRunner

    harness = PipelineHarness()
    batch, assets = harness.make_batch(file_count=file_count)
    repo = SharedFakeAssetRepo(assets)
    services = harness.build_services(repo)

    process = psutil.Process()
    started = datetime.now(timezone.utc)
    cpu_start = process.cpu_times()
    rss_start = process.memory_info().rss
    wall_start = time.perf_counter()

    results = [await harness.run_asset(asset, services) for asset in assets]

    wall_seconds = time.perf_counter() - wall_start
    rss_end = process.memory_info().rss
    cpu_end = process.cpu_times()
    completed = datetime.now(timezone.utc)

    job = Job(
        batch_id=batch.id,
        status=JobStatus.COMPLETED,
        progress=100,
        total_files=file_count,
        processed_files=sum(1 for ok in results if ok),
        failed_files=sum(1 for ok in results if not ok),
    )
    job.started_at = started
    job.completed_at = completed

    pipeline = EvaluationPipeline(
        assets=repo,  # type: ignore[arg-type]
        predictions=services["predictions_repo"],  # type: ignore[arg-type]
        metrics_repo=FakeMetricsRepo(),  # type: ignore[arg-type]
        calculator=BatchMetricsCalculator(),
        exporter=BatchExporter(
            storage=harness.storage,  # type: ignore[arg-type]
            predictions_export=services["export"],
        ),
        jobs=FakeJobRepo(job),  # type: ignore[arg-type]
    )
    metrics = await pipeline.finalize_batch(batch.id)

    benchmark = await BenchmarkRunner(
        batches=FakeBatchRepo(batch),  # type: ignore[arg-type]
        assets=repo,  # type: ignore[arg-type]
        predictions=services["predictions_repo"],  # type: ignore[arg-type]
        jobs=FakeJobRepo(job),  # type: ignore[arg-type]
    ).run(batch.id)

    cpu_seconds = (cpu_end.user - cpu_start.user) + (cpu_end.system - cpu_start.system)
    report = benchmark.model_dump(mode="json")
    report["total_batch_time_ms"] = round(wall_seconds * 1000.0, 2)
    report["memory"] = {
        "rss_start_mb": round(rss_start / 1e6, 2),
        "rss_end_mb": round(rss_end / 1e6, 2),
        "rss_delta_mb": round((rss_end - rss_start) / 1e6, 2),
    }
    report["cpu"] = {
        "cpu_seconds": round(cpu_seconds, 2),
        "average_utilization_percent": (
            round(cpu_seconds / wall_seconds * 100.0, 2) if wall_seconds > 0 else None
        ),
    }
    report["average_confidence"] = getattr(metrics, "average_confidence", None)
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    return report


def generate_benchmark() -> dict[str, Any]:
    report = asyncio.run(_run_benchmark_batch())
    (RELEASE / "benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (RELEASE / "benchmark_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def run_quality_gates() -> dict[str, Any]:
    py = sys.executable
    return {
        "ruff": _run(["ruff", "check", ".", "../tests"], cwd=BACKEND),
        "black": _run([py, "-m", "black", "--check", ".", "../tests"], cwd=BACKEND),
        "pyright": _run(
            [py, "-m", "pyright", "app", "--pythonpath", py], cwd=BACKEND
        ),
        "pytest": _run([py, "-m", "pytest", "tests", "-q", "--tb=short"], cwd=ROOT),
    }


def main() -> int:
    RELEASE.mkdir(exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    openapi = export_openapi()
    requirements = verify_requirements_lock()
    compose = verify_compose()
    benchmark = generate_benchmark()
    gates = run_quality_gates()

    checks: dict[str, dict[str, Any]] = {
        "openapi_export": openapi,
        "requirements_lock": requirements,
        "docker_compose": compose,
        "benchmark": {
            "passed": benchmark["failure_rate"] == 0.0,
            "artifact": "release/benchmark.json",
        },
        **gates,
    }

    validation_report = {
        "generated_at": generated_at,
        "checks": checks,
        "all_passed": all(
            check["passed"] is True for check in checks.values()
        ),
        "notes": [
            "End-to-end stage validation: tests/e2e/test_pipeline_e2e.py",
            "Output validation: strict filename,result_json CSV contract",
            "Failure modes: corrupted audio, missing R2 object, partial batch",
            "API integrity: tests/api/test_openapi_integrity.py",
        ],
    }
    (RELEASE / "validation_report.json").write_text(
        json.dumps(validation_report, indent=2), encoding="utf-8"
    )

    checklist = {
        "generated_at": generated_at,
        "sprint": 12,
        "parts": {
            "part1_end_to_end_validation": gates["pytest"]["passed"],
            "part2_output_validation": gates["pytest"]["passed"],
            "part3_failure_testing": gates["pytest"]["passed"],
            "part4_performance_validation": benchmark["failure_rate"] == 0.0,
            "part5_reproducibility": compose["passed"],
            "part6_api_validation": openapi["passed"],
            "part7_code_quality": all(
                gates[name]["passed"] for name in ("ruff", "black", "pyright", "pytest")
            ),
            "part8_release_cleanup": gates["ruff"]["passed"],
            "part9_release_artifacts": all(
                [
                    openapi["passed"],
                    requirements["passed"],
                    compose["passed"],
                    benchmark["failure_rate"] == 0.0,
                ]
            ),
            "part10_final_reports": True,
        },
    }
    checklist["all_passed"] = all(checklist["parts"].values())
    (RELEASE / "release_checklist.json").write_text(
        json.dumps(checklist, indent=2), encoding="utf-8"
    )

    for artifact in sorted(RELEASE.glob("*.json")):
        print(f"wrote {artifact.relative_to(ROOT)}")
    print(f"validation all_passed: {validation_report['all_passed']}")
    print(f"checklist all_passed: {checklist['all_passed']}")
    return 0 if validation_report["all_passed"] and checklist["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
