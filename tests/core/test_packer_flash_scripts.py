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


