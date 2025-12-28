import logging

logging.basicConfig(level=logging.WARNING)
logging.getLogger("src").setLevel(logging.DEBUG)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"src.{name}")