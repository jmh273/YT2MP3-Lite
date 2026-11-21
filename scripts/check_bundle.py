"""打包守門:YT2MP3-Lite 的發行包裡不准出現 Google 憑證或 Google API 套件。

用法:python scripts/check_bundle.py <bundle_dir>
    bundle_dir = PyInstaller onedir 輸出(backend/dist/yt2mp3-lite)

通過印 OK 並回 0;違規逐條列出並回 1;看不到錨點(exe、_internal)回 2,
避免「掃了一個空資料夾所以沒找到違規」被當成通過。
輸出刻意只用 ASCII:CI 的 Windows 管線編碼是 cp1252,印中文會直接丟例外。
"""
from __future__ import annotations

import pathlib
import sys

EXE_NAME = "yt2mp3-lite.exe"

# 任何位置出現這些檔名都算違規
FORBIDDEN_FILES = ("client_secret.json", "token.json")

# _internal/ 底下出現這些頂層套件(資料夾或 .dist-info)都算違規
FORBIDDEN_PACKAGES = (
    "google",
    "google_auth",
    "google_api_python_client",
    "googleapiclient",
    "google_auth_oauthlib",
    "google_auth_httplib2",
    "oauthlib",
    "httplib2",
)


def check_bundle(bundle: pathlib.Path) -> tuple[int, list[str]]:
    """回傳 (exit_code, 訊息)。0 = 通過,1 = 有違規,2 = 錨點不存在(不是有效的 bundle)。"""
    internal = bundle / "_internal"
    if not (bundle / EXE_NAME).is_file() or not internal.is_dir():
        return 2, [f"not a valid bundle (missing {EXE_NAME} or _internal/): {bundle}"]

    problems: list[str] = []
    for path in bundle.rglob("*"):
        if path.name.lower() in FORBIDDEN_FILES:
            problems.append(f"forbidden file: {path.relative_to(bundle)}")

    for entry in internal.iterdir():
        name = entry.name.lower()
        top = name.split("-")[0] if name.endswith(".dist-info") else name
        top = top.removesuffix(".py")
        if top in FORBIDDEN_PACKAGES:
            problems.append(f"forbidden package: _internal/{entry.name}")

    return (1, problems) if problems else (0, [])


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python scripts/check_bundle.py <bundle_dir>")
        return 2
    code, messages = check_bundle(pathlib.Path(argv[1]))
    for m in messages:
        print(f"[check_bundle] {m}")
    if code == 0:
        print("[check_bundle] OK: no Google credentials or Google API packages in bundle")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
