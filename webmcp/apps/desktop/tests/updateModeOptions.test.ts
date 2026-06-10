import assert from "node:assert/strict";
import test from "node:test";

import {
  UPDATE_MODE_OPTIONS,
  discoveryProviderForUpdateMode,
  updateModeFromDiscoveryProvider
} from "../src/features/update-workflow/model/updateModeOptions.ts";

test("presents update modes in user-facing language", () => {
  assert.deepEqual(
    UPDATE_MODE_OPTIONS.map((option) => option.label),
    ["코드만 보고 수정", "브라우저를 조작하며 수정"]
  );
});

test("maps user-facing update modes to CLI discovery providers", () => {
  assert.equal(discoveryProviderForUpdateMode("code-only"), "none");
  assert.equal(discoveryProviderForUpdateMode("browser"), "webwright");
});

test("maps legacy discovery providers back to a supported update mode", () => {
  assert.equal(updateModeFromDiscoveryProvider("none"), "code-only");
  assert.equal(updateModeFromDiscoveryProvider("static"), "code-only");
  assert.equal(updateModeFromDiscoveryProvider("webwright"), "browser");
});
