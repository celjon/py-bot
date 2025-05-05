# src/lib/utils/file_utils.py
import os
import time
import aiohttp
import tempfile
from typing import Optional


async def download_file(url: str, filename: Optional[str] = None) -> str:
    """
    Скачивает файл по URL

    Args:
        url: URL файла
        filename: Имя файла (если None, будет сгенерировано случайное имя)

    Returns:
        str: Путь к скачанному файлу
    """
    if not filename:
        filename = f"tmp_{int(time.time())}"

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                with open(file_path, "wb") as f:
                    f.write(await response.read())
                return file_path
            else:
                raise Exception(f"Failed to download file: {response.status}")