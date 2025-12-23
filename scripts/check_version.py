"""
Check for new Lychee Slicer version and update manifest.

This script:
1. Fetches the latest version from the download page
2. Compares with the current version in the manifest
3. Downloads the new .deb file and calculates SHA256
4. Updates the manifest file with new version info
5. Outputs information for GitHub Actions
"""

import hashlib
import os
import re
import sys

import requests
from bs4 import BeautifulSoup
from ruamel.yaml import YAML

yaml = YAML()

yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096  # Prevent line wrapping

def fetch_latest_version():
    """Fetch the latest version from the download page."""
    print("📡 Fetching download page...")
    response = requests.get('https://mango3d.io/download-lychee-slicer', timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract version from the main heading (search all h1 tags)
    print("🔍 Looking for latest version...")
    headings = soup.find_all('h1')

    for heading in headings:
        version_match = re.search(r'Download Lychee Slicer ([\d.]+)', heading.text)
        if version_match:
            return version_match.group(1)

    heading_texts = [heading.text.strip() for heading in headings]
    raise ValueError(
        f"Could not find version in any h1 tag. Found {len(headings)} h1 tags. "
        f"Headings found: {heading_texts}"
    )


def read_current_version(manifest_path):
    """Read current version from the manifest file."""
    print("📄 Reading current manifest...")
    with open(manifest_path, 'r') as f:
        manifest = yaml.load(f)

    for module in manifest['modules']:
        if module['name'] == 'lycheeslicer':
            for source in module['sources']:
                if source.get('type') == 'extra-data':
                    url = source['url']
                    version_match = re.search(r'LycheeSlicer-([\d.]+)\.deb', url)
                    if version_match:
                        return version_match.group(1), source

    raise ValueError("Could not find extra-data source in manifest")


def download_and_hash(url):
    """Download file and calculate SHA256 hash and size."""
    print(f"⬇️  Downloading: {url}")
    print("   (This may take a while, the file is ~120MB)")

    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()

    sha256_hash = hashlib.sha256()
    size = 0
    downloaded_mb = 0

    for chunk in response.iter_content(chunk_size=8192):
        sha256_hash.update(chunk)
        size += len(chunk)

        # Progress indicator
        new_mb = size // (1024 * 1024)
        if new_mb > downloaded_mb:
            downloaded_mb = new_mb
            print(f"   Downloaded: {downloaded_mb} MB", end='\r')

    print()  # New line after progress
    return sha256_hash.hexdigest(), size


def update_manifest(manifest_path, new_url, new_sha256, new_size):
    """Update the manifest file with new version information."""
    print("✏️  Updating manifest...")

    with open(manifest_path, 'r') as f:
        manifest = yaml.load(f)

    # Update the extra-data source
    for module in manifest['modules']:
        if module['name'] == 'lycheeslicer':
            for source in module['sources']:
                if source.get('type') == 'extra-data':
                    source['url'] = new_url
                    source['sha256'] = new_sha256
                    source['size'] = new_size

    # Write back
    with open(manifest_path, 'w') as f:
        yaml.dump(manifest, f)


def write_github_output(key, value):
    """Write output for GitHub Actions."""
    github_output = os.getenv('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{key}={value}\n")


def main():
    manifest_path = 'io.mango3d.LycheeSlicer.yml'

    try:
        # Fetch latest version
        new_version = fetch_latest_version()
        print(f"✅ Latest version found: {new_version}")
        print()

        # Read current version
        current_version, current_source = read_current_version(manifest_path)
        print(f"   Current version: {current_version}")
        print(f"   Current URL: {current_source['url']}")
        print(f"   Current SHA256: {current_source['sha256']}")
        print(f"   Current size: {current_source['size']}")
        print()

        # Compare versions
        if current_version == new_version:
            print("✅ Already on latest version!")
            write_github_output('UPDATE_NEEDED', 'false')
            write_github_output('CURRENT_VERSION', current_version)
            return 0

        print("🆕 New version available!")
        print(f"   Current: {current_version}")
        print(f"   Latest:  {new_version}")
        print()

        # Construct new URL
        new_url = f"https://mango-lychee.nyc3.cdn.digitaloceanspaces.com/LycheeSlicer-{new_version}.deb"
        print(f"📦 New URL: {new_url}")
        print()

        # Download and calculate hash
        new_sha256, new_size = download_and_hash(new_url)

        print()
        print("=" * 60)
        print("📊 Results")
        print("=" * 60)
        print(f"New version:  {new_version}")
        print(f"New URL:      {new_url}")
        print(f"New SHA256:   {new_sha256}")
        print(f"New size:     {new_size:,} bytes ({new_size / (1024*1024):.2f} MB)")
        print()

        # Update manifest
        update_manifest(manifest_path, new_url, new_sha256, new_size)
        print("✅ Manifest updated successfully!")

        # Write GitHub Actions outputs
        write_github_output('UPDATE_NEEDED', 'true')
        write_github_output('NEW_VERSION', new_version)
        write_github_output('NEW_URL', new_url)
        write_github_output('NEW_SHA256', new_sha256)
        write_github_output('NEW_SIZE', str(new_size))

        return 0

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
