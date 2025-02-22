import os
import re
import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import PyPDF2

from schedule_service import ScheduleService

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
    headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    print(f"Status code: {response.status_code}")
    print(response.text[:500])  # Print the first 500 characters of the page
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the exact button with the specified class and onclick attributes containing PDF links
    buttons = soup.find_all('button', {'title': 'Download'}, onclick=True)
    print(f"Found {len(buttons)} buttons")
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

# Route to view all files in the pdf_downloads folder
@app.route('/files/list', methods=['GET'])
def list_all_files():
    folder_path = 'pdf_downloads'
    
    # Check if the folder exists
    if not os.path.exists(folder_path):
        return jsonify({'error': 'Folder not found'}), 404
    
    # Get a list of files in the folder
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    
    return jsonify({'files': files})

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

pdf_downloads = 'pdf_downloads'
app.config['pdf_downloads'] = pdf_downloads

places_map = []

class PlaceMap:
    def __init__(self, name, times=None, next_stop=None, prev_stop=None):
        self.name = name
        self.times = times if times else []
        self.next = next_stop
        self.prev = prev_stop

def add_place(place):
    existing_place = next((p for p in places_map if p['name'] == place['name']), None)
    if existing_place:
        existing_place['times'] = list(set(existing_place['times'] + place['times']))
    else:
        places_map.append(place)

def is_place(text):
    return not (':' in text or 'via' in text or '-' in text or text.strip() == '')

def extract_text_from_pdf(pdf_path):
    places_found = []
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + '\n'
        rows = text.split('\n')

        for row in rows:
            inbetweens = row.split('|')
            for i, value in enumerate(inbetweens):
                value = value.strip()
                if is_place(value):
                    times = inbetweens[i + 1:i + 23]
                    place = {
                        'name': value.strip(),
                        'times': times,
                        'next': inbetweens[i + 24] if i + 24 < len(inbetweens) else None,
                        'prev': inbetweens[i - 24] if i - 24 >= 0 else None
                    }
                    add_place(place)
                    if value not in places_found:
                        places_found.append(value.strip())
    return places_found

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Routes Summary</title>
    </head>
    <body>
        <h1>API Routes Summary</h1>
        <ul>
            <li><strong>GET /</strong> - API Overview (this page)</li>
            <li><strong>GET /files/list</strong> - List available PDF files</li>
            <li><strong>GET /download/&lt;filename&gt;</strong> - Download a specific file</li>
            <li><strong>POST /upload</strong> - Upload a new PDF file</li>
            <li><strong>POST /extract</strong> - Extract text from an uploaded PDF</li>
        </ul>
    </body>
    </html>
    """

@app.route('/extract/<filename>', methods=['GET'])
def extract_from_pdf(filename):
    pdf_path = os.path.join(app.config['pdf_downloads'], filename)
    if not os.path.exists(pdf_path):
        return jsonify({'error': 'File not found'}), 404
    places = []
    places = extract_text_from_pdf(pdf_path)
    return jsonify({'places': places, 'placesMap': places_map})




@app.route('/schedules', methods=['GET'])
def get_schedule():
    schedule_service = ScheduleService()
    # Get user location and destination from query parameters
    user_location = request.args.get('user_location')
    dest = request.args.get('destination')

    if not user_location or not dest:
        return jsonify({"error": "Missing user_location or destination"}), 400

    # Call the method to get times for the given locations
    times = schedule_service.find_times_for_location_and_destination(user_location, dest)
    
    # If times were found, return them in the response, otherwise, return a message
    if times:
        return jsonify({"times": times}), 200
    else:
        return jsonify({"message": f"No schedule found for {user_location} to {dest}."}), 404

# Create an endpoint to get all places
@app.route('/places', methods=['GET'])
def get_all_places():
    schedule_service = ScheduleService()
    places = schedule_service.get_all_places()

    if places:
        return jsonify({"places": places})
    else:
        return jsonify({"message": "No places available."}), 404
    
if __name__ == '__main__':
    os.makedirs(pdf_downloads, exist_ok=True)
    app.run(host='0.0.0.0', port=10000)  # Render uses port 10000

