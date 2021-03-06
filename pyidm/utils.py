"""
    pyIDM

    multi-connections internet download manager, based on "pyCuRL/curl", "youtube_dl", and "PySimpleGUI"

    :copyright: (c) 2019-2020 by Mahmoud Elshahat.
    :license: GNU LGPLv3, see LICENSE for more details.
"""

import os
import sys
import io
import pycurl
import plyer
import certifi
import shutil
import zipfile
import subprocess
import py_compile
import shlex
import re
import json
import pyperclip as clipboard

from . import config


def notify(msg, title='', timeout=5):
    # show os notification at tray icon area
    # title=f'{APP_NAME}'
    try:
        plyer.notification.notify(title=title, message=msg, app_name=config.APP_TITLE)
    except Exception as e:
        handle_exceptions(f'plyer notification: {e}')


def handle_exceptions(error):
    if config.TEST_MODE:
        raise error
    else:
        log(error)


def append_parts(segment_names=None, src_folder=None, target_file=None, target_folder=None):
    """expect list of segment_names like ['100-30000', '50000-80000',...]"""

    target_file = os.path.join(target_folder, target_file)

    try:
        with open(target_file, 'rb+') as target:
            for segment_name in segment_names[:]:
                start = int(segment_name.split('-')[0])
                segment_file = os.path.join(src_folder, segment_name)
                with open(segment_file, 'rb') as segment:
                    # no need to fill zeros "if start > size" since seek/write do it automatically
                    target.seek(start)

                    # write part file
                    target.write(segment.read())

                    # remove part name from list
                    segment_names.remove(segment_name)

    except Exception as e:
        log('append part:> ', repr(e))

    finally:
        # it will return the failed segments, or an empty list in case of success
        return segment_names


def get_headers(url, verbose=False):
    """return dictionary of headers"""
    curl_headers = {}

    def header_callback(header_line):
        # quit if main window terminated
        if config.terminate:
            return

        header_line = header_line.decode('iso-8859-1')
        header_line = header_line.lower()

        if ':' not in header_line:
            return

        name, value = header_line.split(':', 1)
        name = name.strip()
        value = value.strip()
        curl_headers[name] = value
        if verbose: print(name, ':', value)

    def write_callback(data):
        return -1  # send terminate flag

    def debug_callback(handle, type, data, size=0, userdata=''):
        """it takes output from curl verbose and pass it to my log function"""
        try:
            log(data.decode("utf-8"))
        except:
            pass
        return 0

    # region curl options
    agent = f"{config.APP_NAME} Download Manager"
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(pycurl.MAXREDIRS, 10)
    c.setopt(pycurl.CONNECTTIMEOUT, 30)
    c.setopt(pycurl.TIMEOUT, 300)
    c.setopt(pycurl.NOSIGNAL, 1)
    c.setopt(pycurl.CAINFO, certifi.where())  # for https sites and ssl cert handling
    c.setopt(pycurl.USERAGENT, agent)
    c.setopt(pycurl.AUTOREFERER, 1)
    c.setopt(pycurl.WRITEFUNCTION, write_callback)
    c.setopt(pycurl.HEADERFUNCTION, header_callback)
    # endregion

    try:
        c.perform()
    except Exception as e:
        if 'Failed writing body' not in str(e):
            handle_exceptions(e)

    # add status code and effective url to headers
    curl_headers['status_code'] = c.getinfo(pycurl.RESPONSE_CODE)
    curl_headers['eff_url'] = c.getinfo(pycurl.EFFECTIVE_URL)

    # return headers
    return curl_headers


def download(url, file_name=None):
    """simple file download, return False if failed,
    :param url: text url link
    :param file_name: if specified it will save file to disk, otherwise it will buffer to memory
    it will return True / buffer or False"""

    file = None
    buffer = None

    # return None if receive a webpage contents instead of a file
    headers = get_headers(url)
    content_type = headers.get('content-type', '')
    if content_type == '' or 'html' in content_type:
        log('download(): server sent an html webpage or invalid url:', url)
        return False

    # pycurl options
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(pycurl.FOLLOWLOCATION, 1) # re-directions
    c.setopt(pycurl.MAXREDIRS, 10)
    c.setopt(pycurl.NOSIGNAL, 1)  # option required for multi-threading safety
    c.setopt(pycurl.NOPROGRESS, 0)  # will use a progress function
    c.setopt(pycurl.CAINFO, certifi.where())  # for https sites and ssl cert handling

    if file_name:
        file = open(file_name, 'wb')
        c.setopt(c.WRITEDATA, file)
    else:
        buffer = io.BytesIO()
        c.setopt(c.WRITEDATA, buffer)

    try:
        c.perform()
        log('download(): done downloading', )
    except Exception as e:
        log(e)
        return False
    finally:
        c.close()
        if file:
            file.close()

    return buffer or True


def size_format(size, tail=''):
    # 1 kb = 1024 byte, 1MB = 1024 KB, 1GB = 1024 MB
    # 1 MB = 1024 * 1024 = 1_048_576 bytes
    # 1 GB = 1024 * 1024 * 1024 = 1_073_741_824 bytes

    try:
        if size == 0: return '---'
        """take size in num of byte and return representation string"""
        if size < 1024:  # less than KB
            s = f'{round(size)} bytes'

        elif 1_048_576 > size >= 1024:  # more than or equal 1 KB and less than MB
            s = f'{round(size / 1024)} KB'
        elif 1_073_741_824 > size >= 1_048_576:  # MB
            s = f'{round(size / 1_048_576, 1)} MB'
        else:  # GB
            s = f'{round(size / 1_073_741_824, 2)} GB'
        return f'{s}{tail}'
    except:
        return size


def time_format(t, tail=''):
    if t == -1:
        return '---'

    try:
        if t <= 60:
            s = f'{round(t)} seconds'
        elif 60 < t <= 3600:
            s = f'{round(t / 60)} minutes'
        elif 3600 < t <= 86400:
            s = f'{round(t / 3600, 1)} hours'
        elif 86400 < t <= 2592000:
            s = f'{round(t / 86400, 1)} days'
        elif 2592000 < t <= 31536000:
            s = f'{round(t / 2592000, 1)} months'
        else:
            s = f'{round(t / 31536000, 1)} years'

        return f'{s}{tail}'
    except:
        return t


def log(*args):
    s = ''
    for arg in args:
        s += str(arg)
        s += ' '
    s = s[:-1]  # remove last space
    s = '>> ' + s

    try:
        print(s)
    except Exception as e:
        print(e)

    try:
        config.main_window_q.put(('log', '\n' + s))
    except Exception as e:
        print(e)


def validate_file_name(f_name):
    # filter for tkinter safe character range
    f_name = ''.join([c for c in f_name if ord(c) in range(65536)])
    safe_string = str()
    char_count = 0
    for c in str(f_name):
        if c in ['\\', '/', ':', '?', '<', '>', '"', '|', '*']:
            safe_string += '_'
        else:
            safe_string += c

        if char_count > 100:
            break
        else:
            char_count += 1
    return safe_string


def size_splitter(size, part_size):
    """Receive file size and return a list of size ranges"""
    result = []

    if size == 0:
        result.append('0-0')
        return result

    # decide num of parts
    span = part_size if part_size <= size else size
    print(f'span={span}, part size = {part_size}')
    parts = max(size // span, 1)  # will be one part if size < span

    x = 0
    size = size - 1  # when we start counting from zero the last byte number should be size - 1
    for i in range(parts):
        y = x + span - 1
        if size - y < span:  # last remaining bytes
            y = size
        result.append(f'{x}-{y}')
        x = y + 1

    return result


def delete_folder(folder):
    try:
        shutil.rmtree(folder)
    except Exception as e:
        log(e)


def get_seg_size(seg):
    # calculate segment size from segment name i.e. 200-1000  gives 801 byte
    a, b = int(seg.split('-')[0]), int(seg.split('-')[1])
    size = b - a + 1 if b > 0 else 0
    return size





def run_command(cmd, verbose=True, shell=False):
    if verbose: log('running command:', cmd)
    error, output = True, f'error running command {cmd}'
    try:
        if shell:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        else:
            cmd = shlex.split(cmd)  # , posix=False)

            if config.operating_system == 'Windows':
                info = subprocess.STARTUPINFO()
                info.dwFlags = subprocess.STARTF_USESHOWWINDOW
                info.wShowWindow = subprocess.SW_HIDE
            else:
                info = None
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, startupinfo=info)

        error = r.returncode != 0  # True or False
        output = r.stdout.decode('utf-8')
        if verbose: log(f"cmd: '{' '.join(cmd)}' - output: '{output.strip()}'")

    except Exception as e:
        log('error running command: ', ' '.join(cmd), e)
        pass

    return error, output


def print_object(obj):
    if obj is None:
        print(obj, 'is None')
        return
    for k, v in vars(obj).items():
        try:
            print(k, '=', v)
        except:
            pass


def update_object(obj, new_values):
    """update an object attributes from a supplied dictionary"""
    # avoiding obj.__dict__.update(new_values) as it will set a new attribute if it doesn't exist

    for k, v in new_values.items():
        if hasattr(obj, k):
            try:
                setattr(obj, k, v)
            except AttributeError:  # in case of read only attribute
                log(f"update_object(): can't update property: {k}, with value: {v}")
            except Exception as e:
                log(f'update_object(): error, {e}, property: {k}, value: {v}')
    return obj


def truncate(string, length):
    """truncate a string to specified length by adding ... in the middle of the string"""
    # print(len(string), string)
    sep = '...'
    if length < len(sep) + 2:
        string = string[:length]
    elif len(string) > length:
        part = (length - len(sep)) // 2
        remainder = (length - len(sep)) % 2
        string = string[:part + remainder] + sep + string[-part:]
    # print(len(string), string)
    return string


def sort_dictionary(dictionary, descending=True):
    return {k: v for k, v in sorted(dictionary.items(), key=lambda item: item[0], reverse=descending)}


def popup(msg, title=''):
    """Send message to main window to spawn a popup"""
    param = (f'title={title}', msg)
    config.main_window_q.put(('popup', param))



def translate_server_code(code):
    """Lookup server code and return a readable code description"""
    server_codes = {

        # Informational.
        100: ('continue',),
        101: ('switching_protocols',),
        102: ('processing',),
        103: ('checkpoint',),
        122: ('uri_too_long', 'request_uri_too_long'),
        200: ('ok', 'okay', 'all_ok', 'all_okay', 'all_good', '\\o/', '✓'),
        201: ('created',),
        202: ('accepted',),
        203: ('non_authoritative_info', 'non_authoritative_information'),
        204: ('no_content',),
        205: ('reset_content', 'reset'),
        206: ('partial_content', 'partial'),
        207: ('multi_status', 'multiple_status', 'multi_stati', 'multiple_stati'),
        208: ('already_reported',),
        226: ('im_used',),

        # Redirection.
        300: ('multiple_choices',),
        301: ('moved_permanently', 'moved', '\\o-'),
        302: ('found',),
        303: ('see_other', 'other'),
        304: ('not_modified',),
        305: ('use_proxy',),
        306: ('switch_proxy',),
        307: ('temporary_redirect', 'temporary_moved', 'temporary'),
        308: ('permanent_redirect',),

        # Client Error.
        400: ('bad_request', 'bad'),
        401: ('unauthorized',),
        402: ('payment_required', 'payment'),
        403: ('forbidden',),
        404: ('not_found', '-o-'),
        405: ('method_not_allowed', 'not_allowed'),
        406: ('not_acceptable',),
        407: ('proxy_authentication_required', 'proxy_auth', 'proxy_authentication'),
        408: ('request_timeout', 'timeout'),
        409: ('conflict',),
        410: ('gone',),
        411: ('length_required',),
        412: ('precondition_failed', 'precondition'),
        413: ('request_entity_too_large',),
        414: ('request_uri_too_large',),
        415: ('unsupported_media_type', 'unsupported_media', 'media_type'),
        416: ('requested_range_not_satisfiable', 'requested_range', 'range_not_satisfiable'),
        417: ('expectation_failed',),
        418: ('im_a_teapot', 'teapot', 'i_am_a_teapot'),
        421: ('misdirected_request',),
        422: ('unprocessable_entity', 'unprocessable'),
        423: ('locked',),
        424: ('failed_dependency', 'dependency'),
        425: ('unordered_collection', 'unordered'),
        426: ('upgrade_required', 'upgrade'),
        428: ('precondition_required', 'precondition'),
        429: ('too_many_requests', 'too_many'),
        431: ('header_fields_too_large', 'fields_too_large'),
        444: ('no_response', 'none'),
        449: ('retry_with', 'retry'),
        450: ('blocked_by_windows_parental_controls', 'parental_controls'),
        451: ('unavailable_for_legal_reasons', 'legal_reasons'),
        499: ('client_closed_request',),

        # Server Error.
        500: ('internal_server_error', 'server_error', '/o\\', '✗'),
        501: ('not_implemented',),
        502: ('bad_gateway',),
        503: ('service_unavailable', 'unavailable'),
        504: ('gateway_timeout',),
        505: ('http_version_not_supported', 'http_version'),
        506: ('variant_also_negotiates',),
        507: ('insufficient_storage',),
        509: ('bandwidth_limit_exceeded', 'bandwidth'),
        510: ('not_extended',),
        511: ('network_authentication_required', 'network_auth', 'network_authentication'),
    }

    return server_codes.get(code, ' ')[0]


def validate_url(url):
    # below pattern is not tested as a starter it doesn't recognize www. urls
    # improvement required
    pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    match = re.match(pattern, url)
    if match:
        return True
    else:
        return False


def open_file(file):
    try:
        if config.operating_system == 'Windows':
            os.startfile(file)

        elif config.operating_system == 'Linux':
            run_command(f'xdg-open "{file}"', verbose=False)

        elif config.operating_system == 'Darwin':
            run_command(f'open "{file}"', verbose=False)
    except Exception as e:
        print('MainWindow.open_file(): ', e)


def clipboard_read():
    return clipboard.paste()


def clipboard_write(value):
    clipboard.copy(value)


__all__ = [
    'notify', 'handle_exceptions', 'append_parts', 'get_headers', 'download', 'size_format', 'time_format', 'log',
    'validate_file_name', 'size_splitter', 'delete_folder', 'get_seg_size',
    'run_command', 'print_object', 'update_object', 'truncate', 'sort_dictionary', 'popup', 
    'translate_server_code', 'validate_url', 'open_file', 'clipboard_read', 'clipboard_write'
]
