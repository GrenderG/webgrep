import os

from flask import Flask, redirect, request

app = Flask(__name__)

BLOCK_SIZE = 1024
LOG_DIR = '/var/log/'


def qtail(file_path, search=None, lines=20):
    with open(file_path, 'rb') as f:
        total_lines_wanted = lines

        f.seek(0, 2)
        block_end_byte = f.tell()
        lines_to_go = total_lines_wanted
        block_number = -1
        blocks = []
        while lines_to_go > 0 and block_end_byte > 0:
            if block_end_byte - BLOCK_SIZE > 0:
                f.seek(block_number * BLOCK_SIZE, 2)
                blocks.append(f.read(BLOCK_SIZE))
            else:
                f.seek(0, 0)
                blocks.append(f.read(block_end_byte))
            lines_found = blocks[-1].count(b'\n')
            lines_to_go -= lines_found
            block_end_byte -= BLOCK_SIZE
            block_number -= 1
        all_read_text = b''.join(reversed(blocks))

        if search:
            matched_lines = []
            for line in all_read_text.splitlines()[-total_lines_wanted:]:
                if search in str(line):
                    matched_lines.append(line)
            return b'\n'.join(matched_lines)
        return b'\n'.join(all_read_text.splitlines()[-total_lines_wanted:])


@app.route('/')
def main():
    return redirect('/list_logs')


@app.route('/list_logs')
def list_logs():
    file_list = [f for f in os.listdir(LOG_DIR) if os.path.isfile(os.path.join(LOG_DIR, f))]
    return '\n'.join(file_list), 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/logs', methods=['GET'])
def query():
    file_param = request.args.get('f', type=str)
    query_param = request.args.get('q', type=str)
    max_lines_param = request.args.get('l', default=10000, type=int)

    file_path = f'{LOG_DIR}{file_param}'

    # Security checks.
    if not os.path.exists(file_path):
        return 'Error 400: Log file not found, see /list_logs for the list of file names.', 400
    if '..' in file_param or '/' in file_param or '\\' in file_param:
        return 'Error 400: Invalid filename.'

    return (qtail(file_path, search=query_param, lines=max_lines_param), 200,
            {'Content-Type': 'text/plain; charset=utf-8'})


if __name__ == '__main__':
    app.run()
