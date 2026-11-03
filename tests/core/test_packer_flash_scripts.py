import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.core.packer import Repacker


def test_flash_scripts_structure_and_patching():
    """Verify that both Windows and Linux/Mac flash scripts follow the required

    4-stage structure and patch correctly for AB and A-only devices.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ctx = MagicMock()
        ctx.stock_rom_code = "fuxi"
        ctx.base_android_version = "14"
        ctx.target_rom_version = "OS1.0.1.0"
        ctx.is_ab_device = True

        fw_dir = tmp / "firmware-update"
        fw_dir.mkdir()
        (fw_dir / "NON-HLOS.bin").write_bytes(b"dummy")

        bat_dest = tmp / "windows_flash_script.bat"
        shutil.copy2("bin/flash/windows_flash_script.bat", bat_dest)
        sh_dest = tmp / "mac_linux_flash_script.sh"
        shutil.copy2("bin/flash/mac_linux_flash_script.sh", sh_dest)

        # Verify initial contents have the 4 steps in order and NO super.zst references
        for path in (bat_dest, sh_dest):
            content = path.read_text(encoding="utf-8")
            assert "super.zst" not in content
            assert "zstd" not in content
            pos_step1 = content.find("1/4")
            pos_step2 = content.find("2/4")
            pos_step3 = content.find("3/4")
            pos_step4 = content.find("4/4")
            assert -1 < pos_step1 < pos_step2 < pos_step3 < pos_step4

        # Test placeholder replacements and firmware injection (AB device)
        packer = Repacker(ctx)
        packer._process_script_placeholders(bat_dest)
        packer._patch_script_for_firmware(bat_dest, fw_dir)
        packer._process_script_placeholders(sh_dest)
        packer._patch_script_for_firmware(sh_dest, fw_dir)

        bat_content = bat_dest.read_text(encoding="utf-8")
        sh_content = sh_dest.read_text(encoding="utf-8")

        assert "device_code" not in bat_content
        assert "fuxi" in bat_content
        assert "modem_a" in bat_content
        assert "modem_b" in bat_content

        assert "device_code" not in sh_content
        assert "fuxi" in sh_content
        assert "modem_a" in sh_content
        assert "modem_b" in sh_content

        # Test A-only device patching
        ctx.is_ab_device = False
        packer._patch_script_for_a_only(bat_dest)
        packer._patch_script_for_a_only(sh_dest)

        bat_a_only = bat_dest.read_text(encoding="utf-8")
        sh_a_only = sh_dest.read_text(encoding="utf-8")

        # Verify slot _b has been removed for A-only devices (while preserving vendor_boot)
        import re
        assert not re.search(r"_b\b", bat_a_only)
        assert not re.search(r"_b\b", sh_a_only)
        assert "boot.img" in bat_a_only
        assert "boot.img" in sh_a_only
        assert "vendor_boot" in bat_a_only
        assert "vendor_boot" in sh_a_only
        assert "super.img" in bat_a_only
        assert "super.img" in sh_a_only


def test_generate_hybrid_rom_contains_super_img_stored():
    """Verify that hybrid ROM zip contains super.img stored without compression

    and matches the expected flash script contents.
    """
    import zipfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        ctx = MagicMock()
        ctx.stock_rom_code = "fuxi"
        ctx.base_android_version = "14"
        ctx.target_rom_version = "OS1.0.1.0"
        ctx.security_patch = "2024-01-01"
        ctx.is_ab_device = True
        ctx.repack_images_dir = tmp / "repack_images"
        ctx.repack_images_dir.mkdir()
        (ctx.repack_images_dir / "boot.img").write_bytes(b"boot_data")
        (ctx.repack_images_dir / "modem.img").write_bytes(b"modem_data")

        out_dir = tmp / "out"
        out_dir.mkdir()

        packer = Repacker(ctx)
        packer.out_dir = out_dir

        super_img = tmp / "super.img"
        super_img.write_bytes(b"dummy_super_image_bytes")

        packer._generate_flash_script(super_img)

        zip_files = list(out_dir.glob("*.zip"))
        assert len(zip_files) == 1
        hybrid_zip = zip_files[0]
        assert "Hybrid" in hybrid_zip.name

        with zipfile.ZipFile(hybrid_zip, "r") as zf:
            namelist = zf.namelist()
            assert "super.img" in namelist
            assert "super.zst" not in namelist
            assert "META-INF/zstd" not in namelist
            assert "boot.img" in namelist
            assert "firmware-update/modem.img" in namelist
            assert "windows_flash_script.bat" in namelist
            assert "mac_linux_flash_script.sh" in namelist
            assert "META-INF/com/google/android/update-binary" in namelist

            super_info = zf.getinfo("super.img")
            assert super_info.compress_type == zipfile.ZIP_STORED

            # Verify super.img in zip is indeed a sparse image
            with zf.open("super.img") as super_file:
                magic = super_file.read(4)
                assert magic == b"\x3a\xff\x26\xed"

        # Verify previous super_img in workspace was deleted after hybrid zip creation
        assert not super_img.exists()


def test_unsparse_to_sparse_conversion_and_cleanup():
    """Verify raw/unsparse super image conversion to sparse and pre/post cleanup."""
    import zipfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        target_dir = tmp / "target"
        target_dir.mkdir()
        out_dir = tmp / "out"
        out_dir.mkdir()

        ctx = MagicMock()
        ctx.stock_rom_code = "onyx"
        ctx.base_android_version = "15"
        ctx.target_rom_version = "OS2.0.1.0"
        ctx.security_patch = "2025-01-01"
        ctx.is_ab_device = True
        ctx.target_dir = target_dir
        ctx.repack_images_dir = tmp / "repack_images"
        ctx.repack_images_dir.mkdir()
        (ctx.repack_images_dir / "boot.img").write_bytes(b"boot_data")

        packer = Repacker(ctx)
        packer.out_dir = out_dir

        # Test _is_sparse_image helper
        raw_file = target_dir / "raw.img"
        raw_file.write_bytes(b"\x00" * 4096)
        assert not packer._is_sparse_image(raw_file)

        sparse_file = target_dir / "sparse.img"
        sparse_file.write_bytes(b"\x3a\xff\x26\xed" + b"\x00" * 4092)
        assert packer._is_sparse_image(sparse_file)

        # Create previous leftover images in target_dir
        old_raw = target_dir / "super_raw.img"
        old_sparse = target_dir / "super.img"
        old_raw.write_bytes(b"old_raw_data")
        old_sparse.write_bytes(b"old_sparse_data")

        # Mock lpmake and img2simg runs
        def fake_shell_run(cmd):
            if "lpmake" in str(cmd[0]):
                out_idx = cmd.index("--output")
                out_path = Path(cmd[out_idx + 1])
                out_path.write_bytes(b"fake_raw_super_content" * 100)
            elif "img2simg" in str(cmd[0]):
                out_path = Path(cmd[2])
                out_path.write_bytes(b"\x3a\xff\x26\xed" + b"sparse_data")

        packer.shell.run = MagicMock(side_effect=fake_shell_run)
        packer._get_super_size = MagicMock(return_value=13411287040)

        # Run pack_super_image
        packer.pack_super_image()

        # Verify old files and generated files were cleaned up from target_dir
        assert not (target_dir / "super_raw.img").exists()
        assert not (target_dir / "super.img").exists()
        assert not (target_dir / "super_sparse.img").exists()

        # Verify zip was generated with a sparse super.img inside
        zip_files = list(out_dir.glob("*.zip"))
        assert len(zip_files) == 1
        with zipfile.ZipFile(zip_files[0], "r") as zf:
            assert "super.img" in zf.namelist()
            with zf.open("super.img") as sf:
                assert sf.read(4) == b"\x3a\xff\x26\xed"


