#!/usr/bin/env python3
"""
Kingdom Story Photo Scanner
Features:
- Orange Text Extraction (HSV Masking) for Character Names
- Standard Grayscale Preprocessing for Body Text
- Auto-generation of README files
"""

import os
import re
import cv2
import numpy as np
import glob
from datetime import datetime
from pathlib import Path
from PIL import Image
import pytesseract

class KingdomStoryPhotoScanner:
    def __init__(self):
        self.announcement_dirs = []
        self.new_entries = []
       
        # OCR Configuration
        # --psm 6: Assume a single uniform block of text
        self.ocr_config = r'--oem 3 --psm 6 -l chi_tra'

    def find_announcement_folders(self):
        """Find all announcement folders with images"""
        announcements_path = Path("announcements")
        if not announcements_path.exists():
            print("No announcements directory found")
            return []
       
        folders = []
        for folder in announcements_path.iterdir():
            if folder.is_dir() and not folder.name.startswith('.'):
                images_path = folder / "images"
                if images_path.exists():
                    image_files = list(images_path.glob("*.jpg")) + \
                                 list(images_path.glob("*.png")) + \
                                 list(images_path.glob("*.jpeg"))
                    if image_files:
                        folders.append(folder)
       
        return sorted(folders)

    def extract_orange_text(self, image_path):
        """
        Specifically isolates Orange/Red text for OCR (e.g., Character Names).
        """
        try:
            # Load Image
            img = cv2.imread(str(image_path))
            if img is None:
                return ""

            # Convert to HSV
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Define Orange/Red Ranges (0-25 and 160-180)
            lower_red1 = np.array([0, 70, 50])
            upper_red1 = np.array([25, 255, 255])
            lower_red2 = np.array([160, 70, 50])
            upper_red2 = np.array([180, 255, 255])

            # Create Masks
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            combined_mask = cv2.bitwise_or(mask1, mask2)

            # Invert for Tesseract (Black text on White background)
            final_image = cv2.bitwise_not(combined_mask)

            # Upscale for better character recognition
            final_image = cv2.resize(final_image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

            # Denoise
            kernel = np.ones((2,2), np.uint8)
            final_image = cv2.morphologyEx(final_image, cv2.MORPH_OPEN, kernel)

            # Run OCR
            text = pytesseract.image_to_string(final_image, config=self.ocr_config)
            return text.strip()

        except Exception as e:
            print(f"Error extracting orange text: {e}")
            return ""

    def preprocess_standard(self, image_path):
        """Standard preprocessing for body text"""
        try:
            img = cv2.imread(str(image_path))
            if img is None: return None
           
            # Upscale
            img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
           
            # Grayscale & Threshold
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
           
            return thresh
        except Exception:
            return None

    def extract_text_from_image(self, image_path):
        """Combine Orange extraction and Standard extraction"""
       
        # 1. Get Orange Text (High priority for Names)
        orange_text = self.extract_orange_text(image_path)
       
        # 2. Get Standard Text (For body content)
        processed_img = self.preprocess_standard(image_path)
        standard_text = ""
        if processed_img is not None:
            standard_text = pytesseract.image_to_string(processed_img, config=self.ocr_config)
           
        # Combine them
        full_text = self.clean_ocr_text(orange_text + "\n" + standard_text)
        return full_text

    def clean_ocr_text(self, text):
        """Clean and correct common OCR errors"""
        if not text.strip():
            return ""
       
        # Remove empty lines and excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text).strip()
       
        # Basic corrections
        corrections = {
            '技能1': '技能1', '技能l': '技能1',
            '傷害': '傷害', '傷寮': '傷害',
        }
        for wrong, right in corrections.items():
            cleaned = cleaned.replace(wrong, right)
           
        return cleaned

    def extract_character_name(self, text):
        """Find character name in text"""
        if not text: return None
       
        # Look for the specific patterns seen in your screenshots
        patterns = [
            r'推薦書武將\s*([\u4e00-\u9fff]+)',   # Matches "Recommended General [Name]"
            r'新武將\s*([\u4e00-\u9fff]+)',       # Matches "New General [Name]"
            r'武將\s*([\u4e00-\u9fff]+)',         # Matches "General [Name]"
            r'([\u4e00-\u9fff]{2,4})\s*\(',       # Matches "Name ("
        ]
       
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
       
        # Fallback: Look for the first sequence of 2-4 Chinese chars
        # specifically from the "Orange Text" part which usually comes first
        match = re.search(r'^[\u4e00-\u9fff]{2,4}', text)
        if match:
            return match.group(0)
           
        return None

    def generate_title_from_folder(self, folder_name, extracted_text):
        """Generate title combining Folder English Name + OCR Chinese Name"""
        # 1. Get English Base Name
        clean_name = re.sub(r'^\d{4}-\d{1,2}-\d{1,2}-?', '', folder_name)
        clean_name = re.sub(r'Emperor-Rarity-', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'New-Character-', '', clean_name, flags=re.IGNORECASE)
        english_name = clean_name.replace('-', ' ').title()
       
        # 2. Get Chinese Name
        chinese_name = self.extract_character_name(extracted_text)
       
        if chinese_name:
            return f"新武將介紹 - {chinese_name} {english_name}"
        else:
            return f"新武將介紹 - {english_name}"

    def process_folder(self, folder_path):
        print(f"Processing folder: {folder_path.name}")
       
        images_path = folder_path / "images"
        readme_path = folder_path / "README.md"
       
        # Find images
        image_files = sorted(list(images_path.glob("*.jpg")) +
                           list(images_path.glob("*.png")) +
                           list(images_path.glob("*.jpeg")))
       
        if not image_files:
            return False
           
        # Extract text (Focus on first image for Title/Name)
        print(f"  Extracting text...")
        extracted_texts = []
        for img_path in image_files[:3]:
            text = self.extract_text_from_image(img_path)
            if text:
                extracted_texts.append(text)

        all_text = "\n".join(extracted_texts)
       
        # Generate Metadata
        title = self.generate_title_from_folder(folder_path.name, all_text)
       
        # Generate README
        content = f"# {title}\n\n"
        content += f"**Folder:** {folder_path.name}\n"
        content += "\n## Announcement Images\n"
        for img in image_files:
            content += f"![Image](images/{img.name})\n"
           
        if all_text:
            content += "\n## OCR Extracted Text\n"
            content += "```\n" + all_text[:1000] + "\n```\n" # Limit length
           
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
           
        print(f"  Generated README for {title}")
       
        # Save for main README update
        self.new_entries.append({
            'date': datetime.now().strftime("%Y-%m-%d"),
            'title': title,
            'folder': folder_path.name
        })
       
        return True

    def update_main_readme(self):
        """Simple append to main README"""
        if not self.new_entries: return
       
        readme_path = Path("README.md")
        if not readme_path.exists(): return
       
        print(f"Updating main README with {len(self.new_entries)} entries...")
       
        # Construct new lines
        new_lines = []
        for entry in self.new_entries:
            line = f"- **{entry['date']}** - [{entry['title']}](announcements/{entry['folder']}/README.md)"
            new_lines.append(line)
           
        # Read and Update (Simple insertion after header)
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
           
        # Insert after "Recent Announcements" if it exists
        if "### Recent Announcements" in content:
            parts = content.split("### Recent Announcements")
            # Keep header, insert new lines, keep rest
            updated_content = parts[0] + "### Recent Announcements\n" + "\n".join(new_lines) + "\n" + parts[1]
           
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)

    def run(self):
        print("Starting Photo Scanner...")
        folders = self.find_announcement_folders()
        for folder in folders:
            self.process_folder(folder)
        self.update_main_readme()
        print("Done.")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
