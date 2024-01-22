class Config:
    # General config.
    BLOCK_SIZE = 1024
    LOG_DIR = '/tmp'
    DEFAULT_LOG_LINES = 10000000

    # Embedded webserver config.
    BIND_IP = 'localhost'
    BIND_PORT = 5000

    # Basic auth.
    BASIC_AUTH_USERNAME = None
    BASIC_AUTH_PASSWORD = None
