import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# URL of the page with the PDF download buttons
url = 'https://www.gabs.co.za/Timetable.aspx'
file_url = 'https://www.gabs.co.za'

# Create a folder to store PDFs
if not os.path.exists('pdf_downloads'):
    os.makedirs('pdf_downloads')

@app.route('/files', methods=['GET'])
def list_files():
    # Get the HTML content of the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the exact button with the specified class and onclick attributes containing PDF links
    buttons = soup.find_all('button', {'title': 'Download'}, onclick=True)

    pdf_urls = []

    # Extract URLs from the onclick attributes
    for button in buttons:
        onclick_value = button['onclick']
        pdf_match = re.search(r"window\.open\(['\"](.*?)['\"]", onclick_value)
        if pdf_match:
            pdf_url = pdf_match.group(1)
            # Handle relative URLs
            if not pdf_url.startswith('http'):
                pdf_url = file_url + '/' + pdf_url.lstrip('/')
            pdf_urls.append(pdf_url)

    return jsonify({'files': pdf_urls})

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory('pdf_downloads', filename, as_attachment=True)

@app.route('/download-all', methods=['GET'])
def download_all():
    # Get the HTML content of the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the exact button with the specified class and onclick attributes containing PDF links
    buttons = soup.find_all('button', {'title': 'Download'}, onclick=True)

    pdf_urls = []

    # Extract URLs from the onclick attributes
    for button in buttons:
        onclick_value = button['onclick']
        pdf_match = re.search(r"window\.open\(['\"](.*?)['\"]", onclick_value)
        if pdf_match:
            pdf_url = pdf_match.group(1)
            # Handle relative URLs
            if not pdf_url.startswith('http'):
                pdf_url = file_url + '/' + pdf_url.lstrip('/')
            pdf_urls.append(pdf_url)

    # Download each PDF
    for pdf_url in pdf_urls:
        pdf_name = pdf_url.split('/')[-1]
        pdf_path = os.path.join('pdf_downloads', pdf_name)

        print(f"Downloading {pdf_name} from {pdf_url}")

        pdf_response = requests.get(pdf_url, stream=True)
        if pdf_response.status_code == 200:
            with open(pdf_path, 'wb') as pdf_file:
                for chunk in pdf_response.iter_content(chunk_size=1024):
                    pdf_file.write(chunk)
            print(f"Saved: {pdf_path}")
        else:
            print(f"Failed to download: {pdf_url}")

    return jsonify({'status': 'Download complete', 'files': pdf_urls})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)  # Render uses port 10000

