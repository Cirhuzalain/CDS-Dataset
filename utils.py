import json
import uuid
import requests
import os
import logging
from stem import Signal
from pathlib import Path
from stem.control import Controller
from bs4 import BeautifulSoup

def setup_folder():
    if not os.path.exists('seeding'):
        os.makedirs('seeding')
    if not os.path.exists('content'):
        Path('content/img/').mkdir(parents=True, exist_ok=True)

def get_logger(name, file):
    handler = logging.FileHandler(file)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.addHandler(handler)

    return logger

def log_message(message, msg_type):
    if msg_type == 'http':
        logger = get_logger('http', 'error/error_url.log')
    elif msg_type == 'doc':
        logger = get_logger('doc', 'error/error_doc.log')
    elif msg_type == 'sed':
        logger = get_logger('sed', 'error/error_sed.log')
    elif msg_type == 'img':
        logger = get_logger('img', 'error/error_img.log')
    logger.error(message)

def get_headers():
    proxies = {
    'http': 'socks5://127.0.0.1:9050',
    'https': 'socks5://127.0.0.1:9050'
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36', 
                'Accept-Encoding': 'gzip, compress, deflate, identity, br',}
    return headers, proxies

def get_url(url, retry, key):
    connection_attempt = 0
    url = url.rstrip("\n")
    # handle bbc url with amp page
    if '/amp/' in url and key == 'www.bbc.com/news':
        url = url.replace('/amp/', '/')
    if key == 'sw.rfi.fr':
        url = url.replace('sw.rfi.fr', 'www.rfi.fr/sw')
    if key == 'en.rfi.fr':
        url = url.replace('en.rfi.fr', 'www.rfi.fr/en')

    headers, proxies = get_headers()
    while connection_attempt < retry:
        try:
            response = requests.get(url, proxies=proxies, headers=headers)
            template_info = get_template()[key]
            page_details = get_page_details(response.text, template_info, key)
            if len(page_details['document']) > 0 or len(page_details['headline']) > 0:
                return response.text, True
        except Exception:
            pass
        connection_attempt += 1
    return "", False

def get_page_info(page, key, url, retry):
    is_document = False
    template_info = get_template()[key]
    page_details = get_page_details(page, template_info, key)
    image_src = page_details['image_src']

    # DW add domain name 
    if "www.dw.com" in key:
        image_src = f'https://www.dw.com{image_src}'

    if len(page_details['document']) > 0 or len(page_details['headline']) > 0:
        is_document = True

    return {
        'title' : page_details['title'],
        'headline' : page_details['headline'],
        'document' : page_details['document'],
        'image' : image_src,
        'image_desc' : page_details['image_desc'],
        'url': url
    }, is_document

def write_json(content, file_name):
    file_info = f"content/{file_name}"
    with open(file_info, 'w') as fout:
        json.dump(content, fout)

def load_seeding(file_name):
    """
        Loading file seeding file
    """
    file_info = f"seeding/{file_name}"
    with open(file_info, "r") as read_file:
        data = json.load(read_file)
    return data

def switch_ip():
    with Controller.from_port(port = 9051) as controller:
        controller.authenticate()
        controller.signal(Signal.NEWNYM)

def get_custom_src(page, template_info):
    image = page.select(template_info['img'][2])
    img_src = image[0]['data-src'] if len(image) > 0 else ''
    return img_src

def get_page_details(page, template_info, key):
    page_soup = BeautifulSoup(page, 'html.parser')
    
    title = page_soup.select(template_info['title'][0])

    if 'bbc.com' in key and len(title) == 0:
        title = page_soup.select(template_info['title'][1])
        title = title[0].text.strip() if len(title) > 0 else ''

        # handle document which title selector position is different for the remaining attributes (headline, document, img, img_desc)
        idx = 1
        if len(title) == 0:
            title = page_soup.select(template_info['title'][2])
            title = title[0].text.strip() if len(title) > 0 else ''
            idx = 0 if len(title) > 0 else idx

        document = page_soup.select(template_info['document'][idx])
        document = " \n ".join([ p.text for p in document[1:]])

        headline = page_soup.select(template_info['headline'][idx])
        headline = headline[0].text.strip() if len(headline) > 0 else ''

        image = page_soup.select(template_info['img'][idx])
        image_src = image[0]['src'] if len(image) > 0 else ''

        image_src = get_custom_src(page_soup, template_info) if len(image_src) == 0 else image_src

        image_desc = page_soup.select(template_info['img_desc'][idx])
        image_desc = image_desc[0].text.strip() if len(image_desc) > 0 else ''
    else:
        title = title[0].text.strip() if len(title) > 0 else ''
        if key == 'www.voanews.com':
            document = page_soup.select(template_info['document'][0])
            headline = document[0].text if len(document) > 0 else ''
            document = " \n ".join([ p.text for p in document[1:]]) if len(document) > 0 else ''
        else:
            document = page_soup.select(template_info['document'][0])

            if 'bbc.com' in key or 'voaafrique.com' in key or 'voaswahili.com' in key:
                document = " \n ".join([ p.text for p in document[1:]])
                if len(document) == 0:
                    document = page_soup.select(template_info['document'][1])
                    document = "\n".join([el.text for el in document])
            else:
                if 'rfi.fr' in key:
                    document = " \n ".join([ p.text for p in document[:-1]])
                else:
                    document = " \n ".join([ p.text for p in document])

            headline = page_soup.select(template_info['headline'][0])
            headline = headline[0].text.strip() if len(headline) > 0 else ''

        image = page_soup.select(template_info['img'][0])
        if 'dw.com' in key and len(image) == 0:
            image = page_soup.select(template_info['img'][1])

        image_src = image[0]['src'] if len(image) > 0 else ''

        image_src = get_custom_src(page_soup, template_info) if len(image_src) == 0 and 'bbc.com' in key else image_src

        image_desc = page_soup.select(template_info['img_desc'][0])
        image_desc = image_desc[0].text.strip() if len(image_desc) > 0 else ''

    return {
        'title' : title,
        'headline': headline,
        'document': document,
        'image_desc': image_desc,
        'image_src': image_src
    }

def get_template():
    dico = {"sw.rfi.fr" : {'title' : ['article h1'], 'headline' : ['p.t-content__chapo'], 
                            'document' : ['div.t-content__body p'], 'img' : ['img.m-figure__img'], 
                            'img_desc' : ['figcaption.m-figure__caption span']}, 
            "rfi.fr" : {'title' : ['article h1'], 'headline' : ['p.t-content__chapo'], 
                            'document' : ['div.t-content__body p'], 'img' : ['img.m-figure__img'], 
                            'img_desc' : ['figcaption.m-figure__caption span']}, 
            "en.rfi.fr" : {'title' : ['article h1'], 'headline' : ['p.t-content__chapo'], 
                            'document' : ['div.t-content__body p'], 'img' : ['img.m-figure__img'], 
                            'img_desc' : ['figcaption.m-figure__caption span']}, 

            "www.bbc.com/swahili" : {'title' : ['h1.story-body__h1', 'h1.Headline-sc-1kh1qhu-0', 'h2.unit__title'], 
                                      'headline' : ['p.story-body__introduction', 'p.Paragraph-k859h4-0 b'], 
                                      'document' : ['div.story-body__inner p', 'main p.Paragraph-k859h4-0'], 
                                      'img' : ['img.js-image-replace', 'img.StyledImg-sc-7vx2mr-0', '.js-delayed-image-load'], 
                                      'img_desc' : ['span.media-caption__text', 'figcaption.Caption-sc-16x70so-0 p']}, 
            "www.bbc.com/news" : {'title' : ['h1.story-body__h1', 'h1.Headline-sc-1kh1qhu-0', 'h2.unit__title'], 
                                      'headline' : ['p.story-body__introduction', 'p.Paragraph-k859h4-0 b'], 
                                      'document' : ['div.story-body__inner p', 'main p.Paragraph-k859h4-0'], 
                                      'img' : ['img.js-image-replace', 'img.StyledImg-sc-7vx2mr-0', '.js-delayed-image-load'], 
                                      'img_desc' : ['span.media-caption__text', 'figcaption.Caption-sc-16x70so-0 p']},  
            "www.bbc.com/afrique" : {'title' : ['h1.story-body__h1', 'h1.Headline-sc-1kh1qhu-0', 'h2.unit__title'], 
                                      'headline' : ['p.story-body__introduction', 'p.Paragraph-k859h4-0 b'], 
                                      'document' : ['div.story-body__inner p', 'main p.Paragraph-k859h4-0'], 
                                      'img' : ['img.js-image-replace', 'img.StyledImg-sc-7vx2mr-0', '.js-delayed-image-load'], 
                                      'img_desc' : ['span.media-caption__text', 'figcaption.Caption-sc-16x70so-0 p']},  

            "www.dw.com/sw" : {'title' : ['div#bodyContent div h1'], 'headline' : ['p.intro'], 
                                'document' : ['div.group div.longText p'], 'img' : ['a.overlayLink img', 'div.picBox img'], 
                                'img_desc' : ['div.picBox p']}, 
            "www.dw.com/en" : {'title' : ['div#bodyContent div h1'], 'headline' : ['p.intro'], 
                                'document' : ['div.group div.longText p'], 'img' : ['a.overlayLink img', 'div.picBox img'], 
                                'img_desc' : ['div.picBox p']}, 
            "www.dw.com/fr" : {'title' : ['div#bodyContent div h1'], 'headline' : ['p.intro'], 
                                'document' : ['div.group div.longText p'], 'img' : ['a.overlayLink img', 'div.picBox img'], 
                                'img_desc' : ['div.picBox p']}, 

            "www.voanews.com" : {'title' : ['h1.page-header__title span'], 'headline' : [], 'document' : ['div.article__body p'], 
                            'img' : ['figure.media--type-image img'], 'img_desc' : ['figure.media--type-image figcaption']}, 
            "www.voaafrique.com" : {'title' : ['h1.pg-title'], 'headline' : ['div.intro p'], 'document' : ['div.wsw p', 'div.wsw'], 
                                'img' : ['div.img-wrap img'], 'img_desc' : ['figure.media-image span.caption']}, 
            "www.voaswahili.com" : {'title' : ['h1.pg-title'], 'headline' : ['div.intro p'], 'document' : ['div.wsw p', 'div.wsw'], 
                                'img' : ['div.img-wrap img'], 'img_desc' : ['figure.media-image span.caption']}}
    return dico