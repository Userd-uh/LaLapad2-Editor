from pathlib import Path


HTML = (Path(__file__).parent / "templates" / "index.html").read_text(encoding="utf-8")


def test_unavailable_actions_are_disabled_and_labeled():
    assert 'id="connect-ble-btn" disabled aria-disabled="true"' in HTML
    assert 'id="write-firmware-btn" disabled aria-disabled="true"' in HTML
    assert ".unavailable-action::after{content:'不可'" in HTML


def test_write_route_legend_is_explicit():
    assert "変更枠：実機への反映方法" in HTML
    assert "青 = RPCで反映" in HTML
    assert "オレンジ = ファームウェア書込が必要" in HTML


def test_rpc_save_preserves_firmware_only_change_baseline():
    start = HTML.index("async function saveFilesBeforeDeviceWrite()")
    end = HTML.index("async function writeDeviceNow()", start)
    function_source = HTML[start:end]
    assert "pendingWriteSnapshot=deepClone(state.savedSnapshot" in function_source
    assert "state.savedSnapshot=pendingWriteSnapshot" in function_source
    assert function_source.index("await saveAll") < function_source.index(
        "state.savedSnapshot=pendingWriteSnapshot"
    )


def test_file_saved_state_is_separate_from_device_applied_state():
    assert "state.fileSavedSnapshot=deepClone(state.savedSnapshot)" in HTML
    assert "const fileSnapshot=state.fileSavedSnapshot||state.savedSnapshot" in HTML
    assert "stableJson(makeSavedSnapshot())!==stableJson(fileSnapshot)" in HTML


def test_usb_connection_gets_visible_connected_state():
    assert "usbBtn.classList.toggle('usb-connected',usbConnected)" in HTML
    assert "usbBtn.textContent=usbConnected?'USB Connected':'Connect USB'" in HTML


def test_primary_half_switch_ui_and_eight_step_log_are_present():
    assert 'id="primary-side-select"' in HTML
    assert 'onclick="applyPrimarySide()"' in HTML
    assert "async function applyPrimarySide()" in HTML
    assert "logPrimarySwitchInstructions(res.instructions||[])" in HTML
    assert "左右trackpad overlayを同時に切り替えます" in HTML
