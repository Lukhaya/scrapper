import requests
import re

class Route:
    def __init__(self, from_route, to_route, pdf, effective_date, time_table_no):
        self.from_route = from_route
        self.to_route = to_route
        self.pdf = pdf
        self.effective_date = effective_date
        self.time_table_no = time_table_no
        self.places = []
        self.places_map = {}

    def __str__(self):
        return f"Route({self.from_route} -> {self.to_route}, Effective Date: {self.effective_date}, Time Table No: {self.time_table_no})"

    def add_places(self, places):
        self.places = places

    def add_places_map(self, places_map):
        self.places_map = places_map

    def getRouteName(self):
        return f"{self.from_route} -> {self.to_route}"

    def hasPlace(self, placeName):
        return placeName.upper() in self.places

    def getPlaceTimes(self, placeName):
        if self.hasPlace(placeName):
            # Find the place in places_map by name and return its times
            for place in self.places_map:
                if place.get('name') == placeName:
                    return place.get('times', [])
        return []


    def getCurrentPlaceAndDestinationRoute(self, placeName, dest, routes):
        if not self.hasPlace(placeName):
            return None

        # Find route with destination
        destination_route = next((route for route in routes if route.to_route == dest), None)
        if destination_route:
            # Check if the current route has the place and destination route exists
            return destination_route if destination_route.hasPlace(placeName) else None
        return None

    def getCurrentPlaceAndDestinationRouteTimes(self, placeName, dest, routes):
        route = self.getCurrentPlaceAndDestinationRoute(placeName, dest, routes)
        if route:
            return route.getPlaceTimes(placeName)
        return []


class ScheduleService:
    def __init__(self):
        self.base_url = "https://scrapper-rsro.onrender.com"
        self.routes_cache = {}

    # Function to clean up the route data from the file name
    def clean_route_data(self, file_name):
        match = re.match(r"([^_]+)___([^_]+)_from_(\d+)_to_(\d+)_([\d]+)\.pdf", file_name)
        if match:
            from_route = match.group(1).replace('_', ' ').title()
            to_route = match.group(2).replace('_', ' ').title()
            effective_date = match.group(3)
            time_table_no = match.group(5)
            return Route(from_route, to_route, file_name, effective_date, time_table_no)
        return None

    # Function to fetch the list of files
    def get_files_list(self):
        if 'files' in self.routes_cache:
            return self.routes_cache['files']
        url = f"{self.base_url}/files/list"
        response = requests.get(url)
        if response.status_code == 200:
            self.routes_cache['files'] = response.json().get("files", [])
            return self.routes_cache['files']
        return []

    # Function to extract route data from the PDF file
    def extract_route_data(self, pdf_name):
        if pdf_name in self.routes_cache:
            return self.routes_cache[pdf_name]
        url = f"{self.base_url}/extract/{pdf_name}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            self.routes_cache[pdf_name] = data
            return data
        return {}

    # Function to get the routes, process file data and extract additional details
    def get_routes(self):
        if 'routes' in self.routes_cache:
            return self.routes_cache['routes']
        
        files = self.get_files_list()
        routes = []
        
        for file in files:
            route = self.clean_route_data(file)
            if route:
                # Extract more details like stops or schedule data
                extracted_data = self.extract_route_data(route.pdf)
                if extracted_data:
                    route.add_places(extracted_data.get('places', []))
                    route.add_places_map(extracted_data.get('placesMap', []))
                routes.append(route)
        
        self.routes_cache['routes'] = routes
        return routes

    # Method to find times for user location and destination
    def find_times_for_location_and_destination(self, user_location, dest):
        routes = self.get_routes()
        times = []

        # Loop through all routes and fetch times for the user location and destination
        for route in routes:
            # Check if the current route has the user location and destination
            if route.hasPlace(user_location) and route.hasPlace(dest):
                # Get times for the user location
                times_for_user = route.getPlaceTimes(user_location)
                
                if times_for_user:
                    bus_details = f"Bus {route.getRouteName()} will arrive in {user_location} at: {', '.join(times_for_user)}"
                    timeObject = {'times': times_for_user, 'user_location':user_location, 'destination': dest,'bus_route': route.getRouteName(), 'details':bus_details}
                    times.append(timeObject)

        # Output the times found
        if times:
            for time in times:
                print(time['details'])
            return times
        else:
            response = f"No schedule found for {user_location} to {dest}."
            print(response)
            return response

    def clean_places(self, places):
        invalid_patterns = [
            r"^.*\b(STANDARD|SATURDAYS|SUNDAYS|OPERATED|REG|CONDITIONS|CARRIAGE|WEBSITE|LIABLE|ANY|LOSS|INCONVENIENCE|FAILURE|MAINTAIN|VEHICLES|TIMETABLE).*", 
            r"^[A-Za-z]+\.[A-Za-z]+$",  
            r"^[A-Za-z]+\s*[A-Za-z]+$", 
            r"\(",  
            r"^\s*$",  
        ]

        valid_places = []
        
        for place in places:
            is_valid = True
            for pattern in invalid_patterns:
                if re.match(pattern, place):
                    is_valid = False
                    break
            
            if is_valid:
                valid_places.append(place)

        return valid_places

    # Method to get all available places
    def get_all_places(self):
        all_places = set()  
        routes = self.get_routes()  

        for route in routes:
            all_places.update(route.places)  

        return sorted(all_places)

