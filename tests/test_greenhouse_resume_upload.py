from __future__ import annotations

import unittest

from job_apply_agent.greenhouse_resume_upload import (
    GreenhouseUploadError,
    extract_resume_attach_ref,
    snapshot_contains_filename,
)


class GreenhouseResumeUploadTests(unittest.TestCase):
    def test_extracts_resume_attach_ref_before_cover_letter_attach(self) -> None:
        snapshot = """
        - group "Resume/CV*" [ref=f1e148]:
          - generic [ref=f1e149]: Resume/CV*
          - button "Attach" [ref=f1e154] [cursor=pointer]
          - button "Attach" [ref=f1e156]
        - group "Cover Letter" [ref=f1e165]:
          - button "Attach" [ref=f1e171] [cursor=pointer]
        """
        self.assertEqual(extract_resume_attach_ref(snapshot), "f1e154")

    def test_missing_resume_attach_raises(self) -> None:
        snapshot = """
        - group "Cover Letter" [ref=f1e165]:
          - button "Attach" [ref=f1e171] [cursor=pointer]
        """
        with self.assertRaises(GreenhouseUploadError):
            extract_resume_attach_ref(snapshot)

    def test_snapshot_contains_uploaded_filename(self) -> None:
        snapshot = """
        - group "Resume/CV*" [ref=f1e148]:
          - paragraph [ref=f1e483]: Alan-Jiang-SWE-DigitalOcean.pdf
        """
        self.assertTrue(snapshot_contains_filename(snapshot, "Alan-Jiang-SWE-DigitalOcean.pdf"))
        self.assertFalse(snapshot_contains_filename(snapshot, "Alan-Jiang-SRE-DigitalOcean.docx"))


if __name__ == "__main__":
    unittest.main()
