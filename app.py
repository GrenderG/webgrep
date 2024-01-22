import os

from flask import Flask, redirect, request

from config import Config

app = Flask(__name__)
if Config.BASIC_AUTH_USERNAME and Config.BASIC_AUTH_PASSWORD:
    from flask_basicauth import BasicAuth
    basic_auth = BasicAuth(app)
    app.config['BASIC_AUTH_USERNAME'] = Config.BASIC_AUTH_USERNAME
    app.config['BASIC_AUTH_PASSWORD'] = Config.BASIC_AUTH_PASSWORD
    app.config['BASIC_AUTH_FORCE'] = True


def qtail(file_path, search=None, lines=20):
    with open(file_path, 'rb') as f:
        total_lines_wanted = lines

        f.seek(0, 2)
        block_end_byte = f.tell()
        lines_to_go = total_lines_wanted
        block_number = -1
        blocks = []
        while lines_to_go > 0 and block_end_byte > 0:
            if block_end_byte - Config.BLOCK_SIZE > 0:
                f.seek(block_number * Config.BLOCK_SIZE, 2)
                blocks.append(f.read(Config.BLOCK_SIZE))
            else:
                f.seek(0, 0)
                blocks.append(f.read(block_end_byte))
            lines_found = blocks[-1].count(b'\n')
            lines_to_go -= lines_found
            block_end_byte -= Config.BLOCK_SIZE
            block_number -= 1
        all_read_text = b''.join(reversed(blocks))

        if search:
            search_bytes = search.encode('utf-8')
            matched_lines = []
            for line in all_read_text.splitlines()[-total_lines_wanted:]:
                if search_bytes in line:
                    matched_lines.append(line)
            return b'\n'.join(matched_lines)
        return b'\n'.join(all_read_text.splitlines()[-total_lines_wanted:])


@app.route('/', methods=['GET'])
def main():
    return redirect('/list_logs')


@app.route('/list_logs', methods=['GET'])
def list_logs():
    file_list = [f for f in os.listdir(Config.LOG_DIR) if os.path.isfile(os.path.join(Config.LOG_DIR, f))]
    return '\n'.join(file_list), 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/logs', methods=['GET'])
def query():
    file_param = request.args.get('f', type=str)
    query_param = request.args.get('q', type=str)
    max_lines_param = request.args.get('l', default=Config.DEFAULT_LOG_LINES, type=int)

    file_path = os.path.join(Config.LOG_DIR, file_param)

    # Security checks.
    if not os.path.exists(file_path):
        return 'Error 400: Log file not found, see /list_logs for the list of file names.', 400
    if '..' in file_param or '/' in file_param or '\\' in file_param:
        return 'Error 400: Invalid filename.'

    return (qtail(file_path, search=query_param, lines=max_lines_param), 200,
            {'Content-Type': 'text/plain; charset=utf-8'})


if __name__ == '__main__':
    app.run(host=Config.BIND_IP, port=Config.BIND_PORT)
