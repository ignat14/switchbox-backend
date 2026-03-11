#!/usr/bin/env python3
"""End-to-end integration test for the Switchbox system.

Run against a live deployment to verify the full flow:
API -> Postgres -> R2 -> CDN -> SDK

Usage:
    python scripts/integration_test.py \
        --api-url https://api.switchbox.dev \
        --admin-token xxx \
        --cdn-url https://cdn.switchbox.dev

Requirements:
    pip install switchbox-flags httpx
"""

import argparse
import json
import sys
import time
import urllib.request
from dataclasses import dataclass, field

import httpx


@dataclass
class TestResult:
    name: str
    passed: bool
    error: str | None = None


@dataclass
class TestRunner:
    api_url: str
    admin_token: str
    cdn_url: str
    results: list[TestResult] = field(default_factory=list)
    _project_id: str | None = None
    _api_key: str | None = None
    _flag_id: str | None = None
    _rule_id: str | None = None

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.admin_token}"}

    def _api(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self.api_url.rstrip('/')}{path}"
        with httpx.Client(headers=self._headers(), timeout=30) as client:
            return getattr(client, method)(url, **kwargs)

    def run_step(self, name: str, fn):
        try:
            fn()
            self.results.append(TestResult(name=name, passed=True))
            print(f"  PASS  {name}")
        except Exception as e:
            self.results.append(TestResult(name=name, passed=False, error=str(e)))
            print(f"  FAIL  {name}: {e}")

    def step_create_project(self):
        resp = self._api("post", "/projects", json={"name": "integration-test"})
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        self._project_id = data["id"]
        self._api_key = data["api_key"]
        assert self._project_id
        assert self._api_key

    def step_create_flag(self):
        resp = self._api(
            "post",
            f"/projects/{self._project_id}/flags",
            json={
                "key": "integration_test_flag",
                "name": "Integration Test Flag",
                "environment": "dev",
            },
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        self._flag_id = resp.json()["id"]

    def step_add_rule(self):
        resp = self._api(
            "post",
            f"/flags/{self._flag_id}/rules",
            json={
                "attribute": "email",
                "operator": "ends_with",
                "value": "@test.com",
            },
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        self._rule_id = resp.json()["id"]

    def step_toggle_flag_on(self):
        resp = self._api("post", f"/flags/{self._flag_id}/toggle")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert resp.json()["enabled"] is True

    def step_wait_for_cdn(self):
        print("    Waiting 5s for CDN propagation...")
        time.sleep(5)

    def step_verify_cdn_json(self):
        cdn_path = f"{self.cdn_url.rstrip('/')}/{self._project_id}/dev/flags.json"
        req = urllib.request.Request(cdn_path, headers={"User-Agent": "integration-test"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert "flags" in data, "CDN JSON missing 'flags' key"
        assert "integration_test_flag" in data["flags"], "Flag not found in CDN JSON"
        flag = data["flags"]["integration_test_flag"]
        assert flag["enabled"] is True, "Flag not enabled in CDN JSON"
        assert len(flag["rules"]) == 1, "Rule not present in CDN JSON"
        assert flag["rules"][0]["attribute"] == "email"

    def step_verify_sdk_enabled(self):
        from switchbox import Client

        cdn_path = f"{self.cdn_url.rstrip('/')}/{self._project_id}/dev/flags.json"
        with Client(cdn_url=cdn_path, poll_interval=9999) as client:
            # User matching rule
            assert client.enabled(
                "integration_test_flag", user={"user_id": "1", "email": "alice@test.com"}
            ), "SDK should return True for user matching rule"

            # User not matching rule — depends on rollout (0% by default)
            result = client.enabled(
                "integration_test_flag", user={"user_id": "1", "email": "alice@other.com"}
            )
            # With 0% rollout and no rule match, should be False
            assert result is False, "SDK should return False for non-matching user with 0% rollout"

    def step_toggle_flag_off(self):
        resp = self._api("post", f"/flags/{self._flag_id}/toggle")
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def step_verify_sdk_disabled(self):
        print("    Waiting 5s for CDN propagation...")
        time.sleep(5)
        from switchbox import Client

        cdn_path = f"{self.cdn_url.rstrip('/')}/{self._project_id}/dev/flags.json"
        with Client(cdn_url=cdn_path, poll_interval=9999) as client:
            assert client.enabled("integration_test_flag") is False, (
                "SDK should return False for disabled flag"
            )

    def step_delete_flag(self):
        resp = self._api("delete", f"/flags/{self._flag_id}")
        assert resp.status_code == 204

    def step_cleanup_project(self):
        # There's no delete project endpoint, so we just verify we can list
        resp = self._api("get", "/projects")
        assert resp.status_code == 200

    def run(self):
        print("Switchbox Integration Test")
        print("=" * 50)

        steps = [
            ("Create test project", self.step_create_project),
            ("Create test flag", self.step_create_flag),
            ("Add targeting rule", self.step_add_rule),
            ("Toggle flag on", self.step_toggle_flag_on),
            ("Wait for CDN propagation", self.step_wait_for_cdn),
            ("Verify CDN JSON", self.step_verify_cdn_json),
            ("Verify SDK evaluation (enabled)", self.step_verify_sdk_enabled),
            ("Toggle flag off", self.step_toggle_flag_off),
            ("Verify SDK picks up disabled flag", self.step_verify_sdk_disabled),
            ("Delete test flag", self.step_delete_flag),
            ("Cleanup / verify project", self.step_cleanup_project),
        ]

        for name, fn in steps:
            self.run_step(name, fn)

        print()
        print("=" * 50)
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        print(f"Results: {passed} passed, {failed} failed out of {len(self.results)} steps")

        if failed:
            print("\nFailed steps:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.error}")
            return 1
        else:
            print("\nAll steps passed!")
            return 0


def main():
    parser = argparse.ArgumentParser(description="Switchbox end-to-end integration test")
    parser.add_argument("--api-url", required=True, help="Base URL of the Switchbox API")
    parser.add_argument("--admin-token", required=True, help="Admin bearer token")
    parser.add_argument("--cdn-url", required=True, help="Base URL of the CDN (R2 public URL)")
    args = parser.parse_args()

    runner = TestRunner(
        api_url=args.api_url,
        admin_token=args.admin_token,
        cdn_url=args.cdn_url,
    )
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
