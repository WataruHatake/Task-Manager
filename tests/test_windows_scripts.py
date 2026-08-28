from pathlib import Path


def test_windows_powershell_scripts_are_ascii_compatible() -> None:
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"

    for script in scripts_dir.glob("*.ps1"):
        script.read_text(encoding="ascii")
