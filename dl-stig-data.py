import requests
import zipfile
import os
import json
import xmltodict
import re # Still useful for identifying XML files, though less critical without scraping

# Define direct URLs for RHEL 8 and RHEL 9 STIGs
# These links are provided directly by the user.
RHEL8_STIG_URL = "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_RHEL_8_V2R3_STIG.zip"
RHEL9_STIG_URL = "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_RHEL_9_V2R4_STIG.zip"

DOWNLOAD_DIR = "stig_downloads"
EXTRACT_DIR = "stig_extracted"
OUTPUT_JSON_FILE = "rhel_stigs_combined.json"

def download_file(url, download_path):
    """Downloads a file from a given URL."""
    print(f"Attempting to download from: {url}")
    try:
        # DoD Cyber Exchange requires authentication (CAC/PKI) to access these links directly.
        # This script assumes you have configured your system or browser for PKI authentication
        # if accessing these links directly through a script requires it.
        # For typical automated downloads, you might need to handle session or certificate
        # configuration if direct access fails.
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        with open(download_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {download_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        print("Please ensure you have network access to dl.dod.cyber.mil and that")
        print("your environment can handle any potential PKI/CAC authentication required.")
        return False

def unzip_file(zip_path, extract_to_dir):
    """Unzips a ZIP file to a specified directory."""
    print(f"Unzipping {zip_path} to {extract_to_dir}")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to_dir)
        print(f"Successfully unzipped {zip_path}")
        return True
    except zipfile.BadZipFile:
        print(f"Error: {zip_path} is not a valid ZIP file or is corrupted.")
        return False
    except Exception as e:
        print(f"Error unzipping {zip_path}: {e}")
        return False

def xml_to_json(xml_file_path):
    """Converts an XML file to a Python dictionary (JSON compatible)."""
    try:
        with open(xml_file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        return xmltodict.parse(xml_content)
    except Exception as e:
        print(f"Error converting XML {xml_file_path} to JSON: {e}")
        return None

def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(EXTRACT_DIR, exist_ok=True)

    stig_data = []

    # Process RHEL 8
    print("\n--- Processing RHEL 8 STIG ---")
    rhel8_zip_filename = os.path.basename(RHEL8_STIG_URL)
    rhel8_zip_path = os.path.join(DOWNLOAD_DIR, rhel8_zip_filename)

    if download_file(RHEL8_STIG_URL, rhel8_zip_path):
        rhel8_extract_path = os.path.join(EXTRACT_DIR, "rhel8_stig")
        os.makedirs(rhel8_extract_path, exist_ok=True)
        if unzip_file(rhel8_zip_path, rhel8_extract_path):
            # Find all XML files in the extracted directory
            for root, _, files in os.walk(rhel8_extract_path):
                for file in files:
                    if file.lower().endswith(('.xml', '.xccdf')): # STIGs are usually XCCDF XML
                        xml_path = os.path.join(root, file)
                        print(f"Converting RHEL 8 XML: {xml_path}")
                        json_data = xml_to_json(xml_path)
                        if json_data:
                            stig_data.append({"rhel_version": "8", "source_file": file, "data": json_data})
    else:
        print("Skipping RHEL 8 STIG processing due to download failure.")

    # Process RHEL 9
    print("\n--- Processing RHEL 9 STIG ---")
    rhel9_zip_filename = os.path.basename(RHEL9_STIG_URL)
    rhel9_zip_path = os.path.join(DOWNLOAD_DIR, rhel9_zip_filename)

    if download_file(RHEL9_STIG_URL, rhel9_zip_path):
        rhel9_extract_path = os.path.join(EXTRACT_DIR, "rhel9_stig")
        os.makedirs(rhel9_extract_path, exist_ok=True)
        if unzip_file(rhel9_zip_path, rhel9_extract_path):
            # Find all XML files in the extracted directory
            for root, _, files in os.walk(rhel9_extract_path):
                for file in files:
                    if file.lower().endswith(('.xml', '.xccdf')):
                        xml_path = os.path.join(root, file)
                        print(f"Converting RHEL 9 XML: {xml_path}")
                        json_data = xml_to_json(xml_path)
                        if json_data:
                            stig_data.append({"rhel_version": "9", "source_file": file, "data": json_data})
    else:
        print("Skipping RHEL 9 STIG processing due to download failure.")

    # Export combined data to a single JSON file
    if stig_data:
        try:
            with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
                json.dump(stig_data, f, indent=4)
            print(f"\nSuccessfully exported combined STIG data to {OUTPUT_JSON_FILE}")
        except Exception as e:
            print(f"Error writing combined JSON to file: {e}")
    else:
        print("\nNo STIG data was processed to export.")

    # Clean up downloaded and extracted files (optional)
    # import shutil
    # shutil.rmtree(DOWNLOAD_DIR)
    # shutil.rmtree(EXTRACT_DIR)
    # print("Cleaned up download and extraction directories.")

if __name__ == "__main__":
    main()
