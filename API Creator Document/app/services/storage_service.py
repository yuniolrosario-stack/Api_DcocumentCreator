import os
import base64
from pathlib import Path
from typing import Tuple
from app.core.config import settings


class StorageService:
    @staticmethod
    def save_base64_file(base64_data: str, filename: str, subfolder: str = "original") -> Tuple[str, bytes]:
        """
        Decodifica y guarda un archivo Base64 en el almacenamiento local.
        Retorna la ruta absoluta del archivo guardado y los bytes sin procesar.
        """
        folder = settings.storage_path / subfolder
        folder.mkdir(parents=True, exist_ok=True)

        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        file_bytes = base64.b64decode(base64_data)
        safe_filename = Path(filename).name
        file_path = folder / safe_filename

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        return str(file_path), file_bytes

    @staticmethod
    def save_binary_file(file_bytes: bytes, filename: str, subfolder: str = "signed") -> str:
        """Guarda bytes binarios en la carpeta especificada."""
        folder = settings.storage_path / subfolder
        folder.mkdir(parents=True, exist_ok=True)

        safe_filename = Path(filename).name
        file_path = folder / safe_filename

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        return str(file_path)

    @staticmethod
    def read_file_as_base64(file_path: str) -> str:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


storage_service = StorageService()
