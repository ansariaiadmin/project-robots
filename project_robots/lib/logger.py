"""
Logger — simple fallback — v3.2.2 — تاریکی روشن شد
برای پروژه‌هایی که logger ندارن — fallback ساده
"""
import logging
import sys

def get_logger(name: str = __name__):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = get_logger()
