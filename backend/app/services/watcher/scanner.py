"""디렉토리 스캐너: 전체/부분 스캔, 해시 비교."""
import hashlib
from pathlib import Path

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class DirectoryScanner:
    """감시 디렉토리 내 지원 파일 스캔 및 해시 비교."""

    def scan_supported_files(self, directory: str) -> list[str]:
        """디렉토리 내 지원 형식 파일 경로 목록."""
        result = []
        for path in Path(directory).rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                result.append(str(path))
        return sorted(result)

    def compute_hash(self, file_path: str) -> str:
        """파일 SHA-256 해시."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha256.update(block)
        return sha256.hexdigest()
