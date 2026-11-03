from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.config_merger import ConfigMerger
from src.core.packer import Repacker
from src.core.rom.utils import compute_file_hash
from src.utils.contextpatch import ContextPatcher
from src.utils.lpunpack import LpUnpack
from src.utils.sync_engine import ROMSyncEngine


def test_compute_file_hash_chunked(tmp_path: Path):
    test_file = tmp_path / "test.bin"
    # Write 2.5 MB of repeatable data
    content = b"HYPEROS_TEST_CHUNK_DATA" * 100000
    test_file.write_bytes(content)

    import hashlib

    expected_prefix = hashlib.sha256(content).hexdigest()[:16]

    result = compute_file_hash(test_file)
    assert result == expected_prefix


def test_lpunpack_write_extent_chunked(tmp_path: Path):
    super_img = tmp_path / "super.img"
    super_data = b"X" * (2 * 1024 * 1024 + 512)
    super_img.write_bytes(super_data)

    unpack = LpUnpack(SUPER_IMAGE=str(super_img), OUTPUT_DIR=tmp_path / "out")
    out_file = tmp_path / "part.img"

    with open(out_file, "wb") as out_fd:
        # Extract 2MB + 512 bytes starting at offset 512
        unpack._write_extent_to_file(out_fd, offset=512, size=2 * 1024 * 1024, block_size=4096)

    assert out_file.stat().st_size == 2 * 1024 * 1024
    assert out_file.read_bytes() == super_data[512 : 512 + 2 * 1024 * 1024]
    unpack._fd.close()


def test_sync_engine_execute_rules_and_cache(tmp_path: Path):
    source_dir = tmp_path / "source"
    target_dir = tmp_path / "target"
    source_dir.mkdir()
    target_dir.mkdir()

    (source_dir / "test_file.txt").write_text("hello source", encoding="utf-8")
    (target_dir / "test_file.txt").write_text("old target", encoding="utf-8")

    logger = MagicMock()
    ctx = MagicMock()
    syncer = ROMSyncEngine(ctx, logger)

    rules = [{"mode": "file_to_file", "source": "test_file.txt", "target": "test_file.txt"}]

    syncer.execute_rules(source_dir, target_dir, rules)

    assert (target_dir / "test_file.txt").read_text(encoding="utf-8") == "hello source"
    # Ensure caches are populated
    assert syncer._stock_rom_cache is not None
    assert syncer._target_rom_cache is not None


def test_sync_engine_parallel_package_cache(tmp_path: Path):
    target_dir = tmp_path / "apps"
    target_dir.mkdir()

    for i in range(5):
        (target_dir / f"app{i}.apk").write_bytes(b"dummy_apk")

    logger = MagicMock()
    ctx = MagicMock()
    syncer = ROMSyncEngine(ctx, logger)

    def mock_get_apk_pkg(path: Path) -> str:
        return f"com.test.{path.stem}"

    with patch.object(syncer, "_get_apk_package_name", side_effect=mock_get_apk_pkg):
        cache = syncer._get_package_cache(target_dir)

    assert len(cache) == 5
    assert "com.test.app0" in cache
    assert "com.test.app4" in cache


def test_context_patcher_hierarchical_matching(tmp_path: Path):
    fs_file = {
        "/": ["u:object_r:rootfs:s0"],
        "/system": ["u:object_r:system_file:s0"],
        "/system/app": ["u:object_r:system_app_file:s0"],
        "/system/app/Foo": ["u:object_r:system_app_file:s0"],
    }

    patcher = ContextPatcher()
    dir_path = tmp_path / "system"
    (dir_path / "app" / "Foo").mkdir(parents=True)
    new_apk = dir_path / "app" / "Foo" / "Foo.apk"
    new_apk.write_bytes(b"dummy")

    new_fs, added = patcher.context_patch(fs_file, str(dir_path))
    assert added >= 1
    # Check that new entry got parent's context
    matched_entry = None
    for k, v in new_fs.items():
        if "Foo" in k:
            matched_entry = v
            break

    assert matched_entry == ["u:object_r:system_app_file:s0"]


def test_config_merger_desc_index_update():
    merger = ConfigMerger()
    base = {
        "rules": [
            {"description": "rule1", "val": 1},
        ]
    }
    extra = {
        "rules": [
            {"description": "rule2", "val": 2},
            {"description": "rule2", "val": 3},  # Should merge into previous rule2
        ]
    }

    merged = merger.merge(base, extra)
    assert len(merged["rules"]) == 2
    rule2 = [r for r in merged["rules"] if r.get("description") == "rule2"][0]
    assert rule2["val"] == 3


def test_config_merger_dependency_resolution():
    merger = ConfigMerger()
    rules = [
        {"id": "rule_c", "depends_on": ["rule_b"]},
        {"id": "rule_a"},
        {"id": "rule_b", "depends_on": ["rule_a"]},
    ]

    ordered = merger.resolve_dependencies(rules)
    order_ids = [r["id"] for r in ordered]
    assert order_ids == ["rule_a", "rule_b", "rule_c"]


def test_ota_tool_md5_streaming(tmp_path: Path):
    ctx = MagicMock()
    ctx.stock_rom_code = "onyx"
    ctx.target_rom_version = "OS2.0.1.0"
    ctx.security_patch = "2025-01-01"
    ctx.port_android_version = "15"
    ctx.is_port_global_rom = False
    ctx.is_port_eu_rom = False

    repacker = Repacker(ctx)
    repacker.out_dir = tmp_path / "out"
    repacker.out_dir.mkdir()
    repacker.ota_tools_dir = tmp_path / "otatools"
    repacker.product_out = tmp_path / "target_files"

    def fake_run(cmd, env=None):
        # Create the output zip file when the command is called
        zip_arg = cmd[5]
        Path(zip_arg).write_bytes(b"OTA_ZIP_CONTENT_BYTES")

    repacker.shell.run = MagicMock(side_effect=fake_run)
    repacker._run_ota_tool()

    generated_zips = list(repacker.out_dir.glob("*.zip"))
    assert len(generated_zips) == 1
    assert "ota_full" in generated_zips[0].name
