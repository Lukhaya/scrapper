import os
import re
import requests
from bs4 import BeautifulSoup
import PyPDF2
import fitz  # PyMuPDF
import threading


class PDFService:
    def __init__(self, download_folder='pdf_downloads'):
        self.url = 'https://www.gabs.co.za/Timetable.aspx'
        self.file_url = 'https://www.gabs.co.za'
        self.download_folder = download_folder
        os.makedirs(self.download_folder, exist_ok=True)

    def fetch_pdf_links(self):
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(self.url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        buttons = soup.find_all('button', {'title': 'Download'}, onclick=True)
        pdf_urls = []
        for button in buttons:
            pdf_match = re.search(r"window\.open\(['\"](.*?)['\"]", button['onclick'])
            if pdf_match:
                pdf_url = pdf_match.group(1)
                if not pdf_url.startswith('http'):
                    pdf_url = f"{self.file_url}/{pdf_url.lstrip('/')}"
                pdf_urls.append(pdf_url)
        return pdf_urls

    def download_pdfs(self):
        pdf_urls = self.fetch_pdf_links()
        for pdf_url in pdf_urls:
            pdf_name = pdf_url.split('/')[-1]
            pdf_path = os.path.join(self.download_folder, pdf_name)
            response = requests.get(pdf_url, stream=True)
            if response.status_code == 200:
                with open(pdf_path, 'wb') as pdf_file:
                    for chunk in response.iter_content(chunk_size=1024):
                        pdf_file.write(chunk)
        return pdf_urls

    def list_downloaded_pdfs(self):
        return [f for f in os.listdir(self.download_folder) if os.path.isfile(os.path.join(self.download_folder, f))]

class PlaceMapService:
    def __init__(self):
        self.places_map = []
        self.lock = threading.Lock()

    def add_place(self, place):
        with self.lock:
            existing_place = next((p for p in self.places_map if p['name'] == place['name']), None)
            if existing_place:
                existing_place['times'] = list(set(existing_place['times'] + place['times']))
            else:
                self.places_map.append(place)

    def process_text_chunk(self, text, places_found):
        rows = text.split('\n')
        for row in rows:
            inbetweens = row.split('|')
            for i, value in enumerate(inbetweens):
                value = value.strip()
                if self.is_place(value):
                    place = {
                        'name': value,
                        'times': inbetweens[i + 1:i + 23],
                        'next': inbetweens[i + 24] if i + 24 < len(inbetweens) else None,
                        'prev': inbetweens[i - 24] if i - 24 >= 0 else None
                    }
                    self.add_place(place)
                    with self.lock:
                        if value not in places_found:
                            places_found.append(value)

    def extract_text_from_pdf(self, pdf_path):
        places_found = []
        pdf_path = os.path.join('pdf_downloads', pdf_path)
        
        with fitz.open(pdf_path) as doc:
            threads = []
            for page in doc:
                text = page.get_text("text") + '\n'
                thread = threading.Thread(target=self.process_text_chunk, args=(text, places_found))
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()
        
        return places_found

    def is_place(self, text):
        return not (':' in text or 'via' in text or '-' in text or text.strip() == '')

