import argparse
import logging
import json
import uuid
import signal
import sys
import requests as rq
from random import shuffle
from concurrent.futures import wait, ThreadPoolExecutor

from utils import load_seeding, get_template, get_url, get_page_info, write_json, switch_ip, log_message, setup_folder

class InitialSeed:
    """
        Get initial seeding
    """
    def __init__(self, file_name, thread_number):
        """
            Initialize seeding
        """
        self.thread_number = thread_number
        self.final_seed = {}
        self.final_result = [l["cdx-api"] for l in load_seeding(file_name)] 
        self.links = ["sw.rfi.fr", "rfi.fr", "en.rfi.fr", "www.bbc.com/swahili", 
                        "www.bbc.com/news", "www.bbc.com/afrique", "www.dw.com/en", 
                        "www.dw.com/fr", "www.dw.com/sw", "www.voanews.com", "www.voaafrique.com", "www.voaswahili.com"]

    def get_seeding(self):
        """
            Get seeding link from common crawl using seeding detail
        """
        self.get_seeding_links(self.links)
        write_json(self.final_seed, "seeding_final_data.json")
        print("Done saving seeding file !!!")


    def get_seeding_links(self, seedings):
        """
            Save web links results from each common crawl endpoint
        """
        for sed in seedings:
            res = self.parse_common_crawl(self.final_result, sed)
            self.final_seed[sed] = res
            print(f"Done with {sed} !!!")


    def parse_common_crawl(self, link_metadata, link_to_check):
        """
            Parse common crawl URL
        """
        final_links = []
        url = f"{link_to_check}/*"
        for loc in link_metadata:
            link_location = f"{loc}?output=json&fl=url&url="
            try:
                req = rq.get(link_location + url)
                for i in req.text.split("\n"):
                    url_info = json.loads(i)["url"]
                    if url_info not in final_links:
                        final_links.append(url_info)
            except Exception:
                message = f"Seeding error for link : {link_location + url}"
                log_message(message, 'sed')
        return final_links


class TransformDataset:
    """
        Data transformation from seeding link to document
    """

    def __init__(self, file_name, retry, thread_number, sample_number):
        """
            Initialize attributes
        """
        self.thread_number = thread_number
        self.seeding_info = load_seeding(file_name)
        self.current_key = None
        self.retry = retry
        self.page_infos = []
        self.final_data = {}
        self.errors = {'doc' : [], 'http' : []}
        if type(sample_number) == int:
            self.set_seeding_info(sample_number)
        self.set_up_exit()
        
    def set_up_exit(self):
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        print("Stop Script Ctrl+C!")
        self.save_data(True)
        sys.exit(0)

    def set_seeding_info(self, sample_number):
        tmp_dico = {}
        for key in list(self.seeding_info.keys()):
            tmp_info = self.seeding_info[key] 
            shuffle(tmp_info)
            tmp_dico[key] = tmp_info[:sample_number]

        self.seeding_info = tmp_dico

    def start_crawling(self):
        """
            Crawl weblinks using selenium
        """
        current_stats = 0
        for key in list(self.seeding_info.keys()):
            web_links = self.seeding_info[key]
            self.current_key = key

            futures = []
            # scrape and crawl
            with ThreadPoolExecutor(max_workers=self.thread_number) as executor:
                for link in web_links:
                    futures.append(executor.submit(self.get_document, link))

            wait(futures)
            self.final_data[key] = self.page_infos
            current_stats += len(self.page_infos)
            self.page_infos = []
            print(f"Done with : {key}, and current number of downloaded documents {current_stats}")
        
        self.save_data()

    def save_data(self, is_signal=False):
        tmp_name = self.current_key.replace('/', '-')
        hash_file_name = uuid.uuid4().hex
        if is_signal:
            write_json(self.page_infos, f"{tmp_name}{hash_file_name}-success.json")
        else:
            write_json(self.final_data, f"{tmp_name}{hash_file_name}-success.json")
        write_json(self.errors, f"{tmp_name}{hash_file_name}-error.json")

    def get_document(self, url):
        """
            Create document info
        """
        page, is_res = get_url(url, self.retry, self.current_key)
        if is_res:
            document, is_sucess = get_page_info(page, self.current_key, url, self.retry)
            if is_sucess:
                self.page_infos.append(document)
                print(f"Success count : {len(self.page_infos)}, for url : {self.current_key}")
            else:
                message = f"Document problem ( Missing document and headline ) for url : {url}"
                self.errors['doc'].append(message)
        else:
            message = f"HTTP issue, page not found or dns failure for url : {url}"
            self.errors['http'].append(message)
        print(f"Error count : {len(self.errors['http'])}, for url : {self.current_key}")
        switch_ip()


if __name__ == '__main__':

    parser = argparse.ArgumentParser("Scrape RFI/DW/VOA/BBC Weblink")

    parser.add_argument('-c', type=str, help='List of Common Crawl Endpoint')
    parser.add_argument('-r', type=int, help='Number of http retry when DNS fail')
    parser.add_argument('-p', type=int, help='Number Process to launch')
    parser.add_argument('-s', type=str, help='Seeding Common Crawl File containing the initial endpoint')
    parser.add_argument('-b', type=int, help='Sample b links for testing purpose')

    args = parser.parse_args()

    cme_file_name = args.c
    sed_file_name = args.s
    http_retry = args.r if args.r else 1
    process_number = args.p if args.p else 16
    sample_number = args.b if args.b else False

    # Setup required folder
    setup_folder()

    if cme_file_name:
        seeding_info = InitialSeed(cme_file_name, process_number)
        seeding_info.get_seeding()
    elif sed_file_name:
        transform_seed = TransformDataset(sed_file_name, http_retry, process_number, sample_number)
        transform_seed.start_crawling()
    else:
        print("No seeding file was provided")