import requests


def ping_test(url):
    try: 
        # Get request
        headers = {"User-Agent": "CapstoneApp/1.0 (trvpattft@gmail.com)"}
        response = requests.get(url=url,headers=headers ,timeout=5)
        
        if response.status_code == 200: 
            print("success")
            return True
        else: 
            print(f"Error: {response.status_code}")
            
    
    except requests.exceptions.Timeout: 
        print("Request timed out")
        return False
    except requests.exceptions.ConnectionError: 
        print("Connection error, check URL or network connection")
        return False
    except requests.exceptions.RequestException as e: 
        print(f"An error occured: {e}")
        return False
    
    
test_url = "https://world.openfoodfacts.org/api/v3.6/product/3274080005003.json"
ping_test(test_url)