#!/usr/bin/env python3
"""
STIG Data Collection Script
Helps download and prepare STIG documents for the RAG system
"""

import os
import requests
import json
from pathlib import Path
import zipfile
from typing import List, Dict

class STIGDataCollector:
    """Collect STIG documents from various sources"""
    
    def __init__(self, output_dir: str = "stig_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Common STIG download URLs (these may change) - RHEL 9 prioritized
        self.stig_sources = {
            "rhel9": {
                "url": "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_RHEL_9_STIG_V1R3_Manual-xccdf.xml.zip",
                "filename": "rhel9_stig.zip",
                "priority": 1,
                "version": "9"
            },
            "rhel8": {
                "url": "https://dl.dod.cyber.mil/wp-content/uploads/stigs/zip/U_RHEL_8_STIG_V1R12_Manual-xccdf.xml.zip",
                "filename": "rhel8_stig.zip", 
                "priority": 2,
                "version": "8"
            }
        }
    
    def download_stig(self, version: str) -> bool:
        """Download STIG document for specified version"""
        if version not in self.stig_sources:
            print(f"Unknown STIG version: {version}")
            print(f"Available versions: {list(self.stig_sources.keys())}")
            return False
        
        source = self.stig_sources[version]
        output_file = self.output_dir / source["filename"]
        
        try:
            print(f"Downloading {version} STIG...")
            response = requests.get(source["url"], stream=True)
            response.raise_for_status()
            
            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"Downloaded to: {output_file}")
            
            # Extract if it's a zip file
            if output_file.suffix == '.zip':
                self.extract_stig(output_file)
            
            return True
            
        except requests.RequestException as e:
            print(f"Error downloading STIG: {e}")
            return False
    
    def extract_stig(self, zip_path: Path):
        """Extract STIG from zip file"""
        extract_dir = self.output_dir / zip_path.stem
        extract_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            print(f"Extracted to: {extract_dir}")
            
            # Find XML files
            xml_files = list(extract_dir.glob("*.xml"))
            if xml_files:
                print(f"Found XML files: {[f.name for f in xml_files]}")
            
        except zipfile.BadZipFile as e:
            print(f"Error extracting zip: {e}")
    
    def convert_sample_data(self):
        """Create sample STIG data in JSON format for testing - RHEL 9 focused"""
        rhel9_controls = [
            {
                "id": "RHEL-09-211010",
                "title": "RHEL 9 must be configured to verify the signature of packages",
                "severity": "high",
                "version": "9",
                "description": "Changes to any software components can have significant effects on the overall security of the operating system. This requirement ensures the software has not been tampered with and that it has been provided by a trusted vendor.",
                "check": "Verify Red Hat GPG signature checking is configured with the following command: $ sudo grep gpgcheck /etc/dnf/dnf.conf. gpgcheck=1. If \"gpgcheck\" is not set to \"1\", this is a finding.",
                "fix": "Configure Red Hat package signature checking by editing \"/etc/dnf/dnf.conf\" and ensure the following line appears: gpgcheck=1",
                "references": ["CCI-001749"],
                "category": "Package Management"
            },
            {
                "id": "RHEL-09-211015", 
                "title": "RHEL 9 must have the gpgcheck enabled for all repositories",
                "severity": "high",
                "version": "9",
                "description": "Changes to any software components can have significant effects on the overall security of the operating system. This requirement ensures the software has not been tampered with and that it has been provided by a trusted vendor.",
                "check": "Verify that gpgcheck is enabled for all repositories in \"/etc/yum.repos.d/\". Check all repository files with: $ sudo grep -r gpgcheck /etc/yum.repos.d/",
                "fix": "Edit each repository file in \"/etc/yum.repos.d/\" and ensure \"gpgcheck=1\" is set for all repositories.",
                "references": ["CCI-001749"],
                "category": "Package Management"
            },
            {
                "id": "RHEL-09-212010",
                "title": "RHEL 9 must enable kernel lockdown",
                "severity": "medium", 
                "version": "9",
                "description": "Kernel lockdown restricts access to kernel features that may allow arbitrary code execution via kernel modules loading.",
                "check": "Check that kernel lockdown is enabled with: $ sudo cat /sys/kernel/security/lockdown. The output should show either 'integrity' or 'confidentiality'.",
                "fix": "Configure the system to boot with kernel lockdown enabled by adding 'lockdown=integrity' or 'lockdown=confidentiality' to the kernel command line.",
                "references": ["CCI-000381"],
                "category": "System Settings"
            },
            {
                "id": "RHEL-09-671010",
                "title": "RHEL 9 must configure SELinux context type to allow the use of a non-default faillock tally directory",
                "severity": "medium",
                "version": "9", 
                "description": "By limiting the number of failed logon attempts, the risk of unauthorized system access via user password guessing is reduced.",
                "check": "Verify the location of the non-default faillock tally directory with: $ sudo grep tally_dir /etc/security/faillock.conf",
                "fix": "Configure the faillock tally directory and set appropriate SELinux context.",
                "references": ["CCI-000044"],
                "category": "Authentication"
            }
        ]
        
        rhel8_controls = [
            {
                "id": "RHEL-08-010010",
                "title": "RHEL 8 must be configured to verify the signature of packages",
                "severity": "high",
                "version": "8",
                "description": "Changes to any software components can have significant effects on the overall security of the operating system.",
                "check": "Verify Red Hat GPG signature checking is configured with: $ sudo grep gpgcheck /etc/yum.conf",
                "fix": "Configure Red Hat package signature checking by editing /etc/yum.conf and ensure: gpgcheck=1",
                "references": ["CCI-001749"],
                "category": "Package Management"
            },
            {
                "id": "RHEL-08-010020",
                "title": "RHEL 8 must have the gpgcheck enabled for all repositories",
                "severity": "high", 
                "version": "8",
                "description": "Changes to any software components can have significant effects on the overall security of the operating system.",
                "check": "Verify that gpgcheck is enabled for all repositories in /etc/yum.repos.d/",
                "fix": "Edit each repository file in /etc/yum.repos.d/ and ensure gpgcheck=1",
                "references": ["CCI-001749"],
                "category": "Package Management"
            }
        ]
        
        # Create separate files for each version with RHEL 9 as primary
        rhel9_data = {
            "version": "RHEL-9-STIG-V1R3",
            "release_date": "2024-01-01",
            "rhel_version": "9",
            "priority": 1,
            "controls": rhel9_controls
        }
        
        rhel8_data = {
            "version": "RHEL-8-STIG-V1R12", 
            "release_date": "2023-01-01",
            "rhel_version": "8",
            "priority": 2,
            "controls": rhel8_controls
        }
        
        # Save RHEL 9 (primary)
        rhel9_file = self.output_dir / "sample_rhel9_stig.json"
        with open(rhel9_file, 'w') as f:
            json.dump(rhel9_data, f, indent=2)
        
        # Save RHEL 8 (secondary)
        rhel8_file = self.output_dir / "sample_rhel8_stig.json"
        with open(rhel8_file, 'w') as f:
            json.dump(rhel8_data, f, indent=2)
        
        print(f"Created RHEL 9 STIG data (primary): {rhel9_file}")
        print(f"Created RHEL 8 STIG data (secondary): {rhel8_file}")
        return rhel9_file, rhel8_file

def main():
    """Main function for data collection"""
    collector = STIGDataCollector()
    
    print("STIG Data Collector - RHEL 9 Priority")
    print("======================================")
    print("1. Download RHEL 9 STIG (Primary)")
    print("2. Download RHEL 8 STIG (Secondary)") 
    print("3. Download both RHEL 9 and 8 STIGs")
    print("4. Create sample data for testing")
    print("5. Exit")
    
    while True:
        choice = input("\nEnter your choice (1-5): ").strip()
        
        if choice == "1":
            collector.download_stig("rhel9")
        elif choice == "2":
            collector.download_stig("rhel8")
        elif choice == "3":
            collector.download_stig("rhel9")
            collector.download_stig("rhel8")
        elif choice == "4":
            sample_files = collector.convert_sample_data()
            print(f"You can now load this sample data with:")
            print(f"curl -X POST 'http://localhost:8000/load-stig' -d 'file_path={sample_files[0]}'")
            print(f"curl -X POST 'http://localhost:8000/load-stig' -d 'file_path={sample_files[1]}'")
        elif choice == "5":
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()