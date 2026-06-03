from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


DEFAULT_OUTBOX = Path(__file__).with_name("outbox")
DEFAULT_PROOF = DEFAULT_OUTBOX / "greenhouse_resume_upload_latest.json"


class GreenhouseUploadError(RuntimeError):
    pass


def playwright_cli_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / "playwright" / "scripts" / "playwright_cli.sh"


def extract_resume_attach_ref(snapshot_text: str, *, field_label: str = "Resume/CV") -> str:
    lines = snapshot_text.splitlines()
    label_indices = [
        index
        for index, line in enumerate(lines)
        if field_label.lower() in line.lower() and ("group" in line or "generic" in line)
    ]
    attach_pattern = re.compile(r'- button "Attach" \[ref=(?P<ref>[^\]]+)\](?: \[cursor=pointer\])?')
    for index in label_indices:
        for line in lines[index + 1 : index + 80]:
            if "- group " in line and field_label.lower() not in line.lower():
                break
            match = attach_pattern.search(line)
            if match:
                return match.group("ref")
    raise GreenhouseUploadError(f"Could not find Attach button under {field_label!r}")


def snapshot_contains_filename(snapshot_text: str, filename: str) -> bool:
    return filename in snapshot_text


def _run_pwcli(pwcli: Path, args: Sequence[str], *, session: str | None = None) -> subprocess.CompletedProcess[str]:
    if not pwcli.exists():
        raise GreenhouseUploadError(f"Playwright CLI wrapper not found: {pwcli}")
    cmd = [str(pwcli)]
    if session:
        cmd.append(f"-s={session}")
    cmd.extend(args)
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def _require_success(result: subprocess.CompletedProcess[str], action: str) -> None:
    if result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise GreenhouseUploadError(f"{action} failed with exit code {result.returncode}: {detail}")


def run_greenhouse_resume_upload(
    *,
    url: str | None,
    resume_path: Path,
    proof_path: Path = DEFAULT_PROOF,
    session: str | None = None,
    headed: bool = True,
    reuse_current_page: bool = False,
) -> dict:
    resume_path = resume_path.expanduser().resolve()
    if not resume_path.exists():
        raise GreenhouseUploadError(f"Resume file does not exist: {resume_path}")
    if resume_path.suffix.lower() not in {".pdf", ".doc", ".docx", ".txt", ".rtf"}:
        raise GreenhouseUploadError(f"Unsupported Greenhouse resume file type: {resume_path.suffix}")

    pwcli = playwright_cli_path()
    opened_page = False
    if not reuse_current_page:
        if not url:
            raise GreenhouseUploadError("--url is required unless --reuse-current-page is set")
        open_args = ["open", url]
        if headed:
            open_args.append("--headed")
        result = _run_pwcli(pwcli, open_args, session=session)
        _require_success(result, "open")
        opened_page = True

    before = _run_pwcli(pwcli, ["snapshot"], session=session)
    _require_success(before, "snapshot before upload")

    already_uploaded = snapshot_contains_filename(before.stdout, resume_path.name)
    attach_ref = None
    click_result = None
    upload_result = None
    if not already_uploaded:
        attach_ref = extract_resume_attach_ref(before.stdout)
        click_result = _run_pwcli(pwcli, ["click", attach_ref], session=session)
        _require_success(click_result, "click Resume/CV Attach")
        upload_result = _run_pwcli(pwcli, ["upload", str(resume_path)], session=session)
        _require_success(upload_result, "upload resume")
        time.sleep(0.5)

    after = _run_pwcli(pwcli, ["snapshot"], session=session)
    _require_success(after, "snapshot after upload")
    observed = snapshot_contains_filename(after.stdout, resume_path.name)
    if not observed:
        raise GreenhouseUploadError(f"Uploaded filename not observed in page snapshot: {resume_path.name}")

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "platform": "greenhouse",
        "url": url,
        "resume_path": str(resume_path),
        "resume_filename": resume_path.name,
        "session": session or "default",
        "opened_page": opened_page,
        "reuse_current_page": reuse_current_page,
        "already_uploaded_before_run": already_uploaded,
        "attach_ref": attach_ref,
        "upload_observed": observed,
        "submit_clicked": False,
        "final_submit_status": "not_submitted",
        "next_action": "operator_review_before_final_submit",
        "proof": {
            "before_snapshot_contains_filename": already_uploaded,
            "after_snapshot_contains_filename": observed,
            "click_exposed_file_chooser": None if click_result is None else "File chooser" in click_result.stdout,
            "upload_exit_code": None if upload_result is None else upload_result.returncode,
        },
    }
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upload a resume PDF/DOC to a Greenhouse Resume/CV field via Playwright CLI without final submit."
    )
    parser.add_argument("--url", help="Job application URL to open before upload.")
    parser.add_argument("--resume", required=True, type=Path, help="Absolute or relative path to the resume file.")
    parser.add_argument("--proof", type=Path, default=DEFAULT_PROOF, help="Path to write upload proof JSON.")
    parser.add_argument("--session", help="Optional playwright-cli session name.")
    parser.add_argument("--reuse-current-page", action="store_true", help="Use the currently open Playwright page.")
    parser.add_argument("--headless", action="store_true", help="Open browser without --headed.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload = run_greenhouse_resume_upload(
            url=args.url,
            resume_path=args.resume,
            proof_path=args.proof,
            session=args.session,
            headed=not args.headless,
            reuse_current_page=args.reuse_current_page,
        )
    except GreenhouseUploadError as exc:
        print(f"greenhouse resume upload failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
