import collections
import os
import time

from flask import Flask, request, render_template

try:
    # noinspection PyUnresolvedReferences,PyPackageRequirements
    from config import Config
except ModuleNotFoundError:
    print('\033[91m[ERROR] Please rename config.py.dist to config.py and edit it to your liking.\033[0m')
    exit(1)

app = Flask(__name__)
if Config.BASIC_AUTH_ENABLE:
    from flask_basicauth import BasicAuth

    class MultiUserBasicAuth(BasicAuth):
        # override
        def check_credentials(self, username, password):
            return username in Config.BASIC_AUTH_USERS and Config.BASIC_AUTH_USERS[username] == password

    basic_auth = MultiUserBasicAuth(app)
    app.config['BASIC_AUTH_FORCE'] = True


# TODO: Extra line breaks are being added when a line is split in the middle due to block size limitations.
#  Find a clean way to prevent these splits.
def qtail(file_path, search=None, lines=20):
    # TODO: Hackfix for people that haven't updated their config file. Remove this ASAP as soon as a proper config
    #  system is in place.
    try:
        max_memory = Config.MAX_MEMORY_ALLOCATION
    except AttributeError:
        max_memory = 4 * 1024 * 1024 * 1024  # Default 4GB max memory usage.
    try:
        processing_timeout = Config.PROCESSING_TIMEOUT
    except AttributeError:
        processing_timeout = 50  # 50 seconds.
    # TODO: End of hackfix.
    block_size = Config.BLOCK_SIZE
    start_time = time.time()

    with open(file_path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        block_end_byte = file_size
        lines_to_go = lines

        # Store only needed matching lines.
        line_buffer = collections.deque(maxlen=lines)
        line_buffer_memory = 0  # Track memory usage of line_buffer.
        remainder = b''  # Store any remainder from previous block to merge split lines.

        while lines_to_go > 0 and block_end_byte > 0:
            # Read only up to the remaining file size.
            read_size = min(block_size, block_end_byte)
            f.seek(block_end_byte - read_size, os.SEEK_SET)
            block = f.read(read_size)
            block_end_byte -= read_size

            block_lines = block.splitlines()
            # We need to ensure that lines are not split in the middle. If the first line in this block is incomplete,
            # merge it with remainder from the next block.
            if remainder:
                if block_lines:
                    block_lines[-1] += remainder  # Merge the split line.
                else:
                    block_lines = [remainder]  # If block is empty, remainder is the only line.
                remainder = b''  # Clear remainder after merging.

            # If the block starts with an incomplete line, store it as remainder for the next iteration.
            if block_lines and block[0] != b'\n'[0]:
                remainder = block_lines.pop(0)

            # Process and apply the search filter to each line.
            for line in reversed(block_lines):
                if search:
                    # Apply search filter: only keep lines that match all search strings.
                    search_strings = [s.encode('utf-8') for s in search.split('|')]
                    if all(s in line for s in search_strings):
                        # Add the line if it matches the search.
                        if len(line_buffer) < lines:
                            line_buffer.appendleft(line)
                            line_buffer_memory += len(line)  # Track memory used by this line.
                        else:
                            break
                else:
                    # No search, just store the line.
                    if len(line_buffer) < lines:
                        line_buffer.appendleft(line)
                        line_buffer_memory += len(line)  # Track memory used by this line.
                    else:
                        break

            # Stop processing further if memory limit was exceeded.
            if line_buffer_memory > max_memory:
                break

            # Stop processing further if processing time exceeded the limit.
            if time.time() - start_time > processing_timeout:
                break

        # If there is still an unprocessed remainder, apply the search filter before adding it.
        if remainder:
            if not search or all(s in remainder for s in [s.encode('utf-8') for s in search.split('|')]):
                if len(line_buffer) < lines:
                    line_buffer.appendleft(remainder)

        # Return the lines collected (matching or all lines).
        return b'\n'.join(line_buffer)


@app.route('/', methods=['GET'])
def main():
    return render_template('index.html', default_log_lines=Config.DEFAULT_LOG_LINES, title='webgrep')


@app.route('/list_files', methods=['GET'])
def list_logs():
    file_list = [f for f in os.listdir(Config.LOG_DIR)
                 if os.path.isfile(os.path.join(Config.LOG_DIR, f)) and not any(
            f.endswith(ext) for ext in Config.IGNORE_FILE_EXTENSIONS)]
    return '\n'.join(sorted(file_list)), 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/query', methods=['GET'])
def query():
    file_param = request.args.get('f', type=str)
    query_param = request.args.get('q', type=str)
    max_lines_param = request.args.get('l', default=Config.DEFAULT_LOG_LINES, type=int)

    file_path = os.path.join(Config.LOG_DIR, file_param)

    # Security checks.
    if not os.path.exists(file_path) or any(file_path.endswith(ext) for ext in Config.IGNORE_FILE_EXTENSIONS):
        return ('HTTP ERROR 400: File not found, see /list_files for the list of file names.', 400,
                {'Content-Type': 'text/plain; charset=utf-8'})
    if '..' in file_param or '/' in file_param or '\\' in file_param:
        return 'HTTP ERROR 400: Invalid filename.', 400, {'Content-Type': 'text/plain; charset=utf-8'}

    try:
        return (qtail(file_path, search=query_param, lines=max_lines_param), 200,
                {'Content-Type': 'text/plain; charset=utf-8'})
    except MemoryError:
        return ('HTTP ERROR 500: Not enough memory to handle this request.', 500,
                {'Content-Type': 'text/plain; charset=utf-8'})
    except PermissionError:
        return ('HTTP ERROR 500: Not enough permissions to view this file.', 500,
                {'Content-Type': 'text/plain; charset=utf-8'})


if __name__ == '__main__':
    app.run(host=Config.BIND_IP, port=Config.BIND_PORT)
