#!/usr/bin/env python3
"""
Kingdom Story Photo Scanner - IMPROVED VERSION
Features:
- Two-Pass OCR: Orange text for headers/names + Standard grayscale for body text
- Better text extraction and character recognition
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
       
        # OCR Configuration for Traditional Chinese
        self.ocr_config = r'--oem 3 --psm 6 -l chi_tra'
        
        # For sections with more sparse text
        self.ocr_config_sparse = r'--oem 3 --psm 11 -l chi_tra'

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
        Extract Orange/Red text for headers and character names.
        Uses HSV color masking to isolate orange text.
        """
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return ""

            # Convert to HSV color space
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # Define Orange/Red color ranges
            # Range 1: Orange (0-25 in hue)
            lower_red1 = np.array([0, 70, 50])
            upper_red1 = np.array([25, 255, 255])
            
            # Range 2: Red (160-180 in hue)
            lower_red2 = np.array([160, 70, 50])
            upper_red2 = np.array([180, 255, 255])

            # Create masks for both ranges
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            combined_mask = cv2.bitwise_or(mask1, mask2)

            # Invert mask (Tesseract expects black text on white background)
            inverted = cv2.bitwise_not(combined_mask)

            # Upscale for better character recognition
            upscaled = cv2.resize(inverted, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

            # Denoise with morphological operations
            kernel = np.ones((2,2), np.uint8)
            cleaned = cv2.morphologyEx(upscaled, cv2.MORPH_OPEN, kernel)

            # Run OCR
            text = pytesseract.image_to_string(cleaned, config=self.ocr_config_sparse)
            return text.strip()

        except Exception as e:
            print(f"Error extracting orange text: {e}")
            return ""

    def extract_standard_text(self, image_path):
        """
        Extract all text using standard grayscale preprocessing.
        This works best for body text, descriptions, and general content.
        """
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return ""
           
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Upscale for better recognition
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
           
            # Apply Otsu's thresholding for automatic threshold selection
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
           
            # Run OCR
            text = pytesseract.image_to_string(thresh, config=self.ocr_config)
            return text.strip()

        except Exception as e:
            print(f"Error extracting standard text: {e}")
            return ""

    def extract_text_from_image(self, image_path):
        """
        Two-pass OCR approach:
        1. Extract orange text (headers, character names)
        2. Extract standard text (body content, skills, descriptions)
        3. Combine with priority to orange text for character names
        """
        print(f"    Extracting text from: {image_path.name}")
        
        # Pass 1: Orange text (headers and character names)
        orange_text = self.extract_orange_text(image_path)
        
        # Pass 2: Standard grayscale (all text including body)
        standard_text = self.extract_standard_text(image_path)
        
        # Combine results
        # Orange text gets priority for character name extraction
        combined_text = {
            'orange': self.clean_ocr_text(orange_text),
            'standard': self.clean_ocr_text(standard_text),
            'full': self.clean_ocr_text(orange_text + "\n\n" + standard_text)
        }
        
        return combined_text

    def clean_ocr_text(self, text):
        """Clean and correct common OCR errors in Traditional Chinese"""
        if not text or not text.strip():
            return ""
       
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', text).strip()
        
        # Common OCR corrections for Traditional Chinese
        corrections = {
            # Number corrections
            '技能1': '技能1', '技能l': '技能1', '技能i': '技能1',
            '技能2': '技能2', '技能z': '技能2',
            '技能3': '技能3',
            '技能4': '技能4',
            
            # Common character corrections
            '傷害': '傷害', '傷寮': '傷害', '傷書': '傷害',
            '攻擊': '攻擊', '攻書': '攻擊',
            '武將': '武將', '武書': '武將',
            '敵人': '敵人', '敵入': '敵人',
            
            # Remove common OCR artifacts
            '|': '', '\\': '', '_': '',
        }
        
        for wrong, right in corrections.items():
            cleaned = cleaned.replace(wrong, right)
           
        return cleaned

    def extract_character_name(self, text_dict):
        """
        Extract character name from OCR text.
        Prioritizes orange text (where names usually appear).
        """
        # Try orange text first (most likely to contain character name)
        orange_text = text_dict.get('orange', '')
        if orange_text:
            name = self._find_name_in_text(orange_text)
            if name:
                return name
        
        # Fallback to full text
        full_text = text_dict.get('full', '')
        if full_text:
            name = self._find_name_in_text(full_text)
            if name:
                return name
                
        return None

    def _find_name_in_text(self, text):
        """Find character name using various patterns"""
        if not text:
            return None
       
        # Pattern 1: After specific keywords
        patterns = [
            r'推薦書武將[：:\s]*([\u4e00-\u9fff]{2,4})',     # Recommended General: [Name]
            r'新武將[：:\s]*([\u4e00-\u9fff]{2,4})',         # New General: [Name]
            r'武將[：:\s]*([\u4e00-\u9fff]{2,4})',           # General: [Name]
            r'介紹[：:\s]*([\u4e00-\u9fff]{2,4})',           # Introduction: [Name]
            r'([\u4e00-\u9fff]{2,4})\s*[（(]',              # Name (
            r'^([\u4e00-\u9fff]{2,4})\s*$',                 # Just a name on its own line
        ]
       
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                name = match.group(1).strip()
                # Validate: name should be 2-4 characters
                if 2 <= len(name) <= 4:
                    return name
       
        # Pattern 2: First sequence of 2-4 Chinese characters
        # (Often appears at the start in orange text)
        lines = text.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            match = re.search(r'[\u4e00-\u9fff]{2,4}', line)
            if match:
                name = match.group(0)
                # Avoid common false positives
                if name not in ['新增', '改版', '武將', '推薦', '介紹', '技能', '皇帝']:
                    return name
           
        return None

    def generate_title_from_folder(self, folder_name, text_dict):
        """
        Generate title combining folder English name + OCR Chinese name.
        """
        # Extract English name from folder
        clean_name = re.sub(r'^\d{4}-\d{1,2}-\d{1,2}-?', '', folder_name)
        clean_name = re.sub(r'Emperor-Rarity-', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'New-Character-', '', clean_name, flags=re.IGNORECASE)
        english_name = clean_name.replace('-', ' ').title()
       
        # Extract Chinese name from OCR
        chinese_name = self.extract_character_name(text_dict)
       
        # Generate title
        if chinese_name:
            return f"新武將介紹 - {chinese_name} ({english_name})"
        else:
            return f"新武將介紹 - {english_name}"

    def process_folder(self, folder_path):
        """Process a single announcement folder"""
        print(f"\n{'='*70}")
        print(f"Processing folder: {folder_path.name}")
        print('='*70)
       
        images_path = folder_path / "images"
        readme_path = folder_path / "README.md"
       
        # Find all images
        image_files = sorted(list(images_path.glob("*.jpg")) +
                           list(images_path.glob("*.png")) +
                           list(images_path.glob("*.jpeg")))
       
        if not image_files:
            print("  ⚠️  No images found")
            return False
           
        print(f"  Found {len(image_files)} images")
        
        # Extract text from first few images (character info usually in first images)
        all_text_dicts = []
        for i, img_path in enumerate(image_files[:3], 1):
            print(f"  [{i}/{min(3, len(image_files))}] Processing {img_path.name}...")
            text_dict = self.extract_text_from_image(img_path)
            if text_dict and text_dict.get('full'):
                all_text_dicts.append(text_dict)
        
        if not all_text_dicts:
            print("  ⚠️  No text extracted from images")
            return False
        
        # Combine all extracted text for README
        combined_orange = '\n\n'.join([t['orange'] for t in all_text_dicts if t.get('orange')])
        combined_standard = '\n\n'.join([t['standard'] for t in all_text_dicts if t.get('standard')])
        
        # Generate title (use first image's text for character name)
        title = self.generate_title_from_folder(folder_path.name, all_text_dicts[0])
        
        print(f"  ✅ Generated title: {title}")
        
        # Generate README content
        content = self._generate_readme_content(
            title=title,
            folder_name=folder_path.name,
            image_files=image_files,
            orange_text=combined_orange,
            standard_text=combined_standard
        )
        
        # Write README
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
           
        print(f"  ✅ Generated README: {readme_path}")
       
        # Save for main README update
        self.new_entries.append({
            'date': datetime.now().strftime("%Y-%m-%d"),
            'title': title,
            'folder': folder_path.name
        })
       
        return True

    def _generate_readme_content(self, title, folder_name, image_files, orange_text, standard_text):
        """Generate README.md content"""
        content = f"# {title}\n\n"
        content += f"**Folder:** `{folder_name}`  \n"
        content += f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        content += "---\n\n"
        content += "## 📷 Announcement Images\n\n"
        
        for img in image_files:
            content += f"![{img.stem}](images/{img.name})\n\n"
        
        content += "---\n\n"
        
        # Show extracted text sections
        if orange_text:
            content += "## 🔶 Character Name & Headers (Orange Text)\n\n"
            content += "```\n"
            content += orange_text[:500]  # Limit length
            if len(orange_text) > 500:
                content += "\n... (truncated)"
            content += "\n```\n\n"
        
        if standard_text:
            content += "## 📝 Skills & Description (Body Text)\n\n"
            content += "```\n"
            content += standard_text[:1500]  # Limit length
            if len(standard_text) > 1500:
                content += "\n... (truncated)"
            content += "\n```\n\n"
        
        content += "---\n\n"
        content += "*Generated by Kingdom Story Photo Scanner*\n"
        
        return content

    def update_main_readme(self):
        """Update main README.md with new entries"""
        if not self.new_entries:
            print("\nNo new entries to add to main README")
            return
       
        readme_path = Path("README.md")
        if not readme_path.exists():
            print("\n⚠️  Main README.md not found")
            return
       
        print(f"\n{'='*70}")
        print(f"Updating main README with {len(self.new_entries)} new entries...")
        print('='*70)
       
        # Create new entry lines
        new_lines = []
        for entry in self.new_entries:
            line = f"- **{entry['date']}** - [{entry['title']}](announcements/{entry['folder']}/README.md)"
            new_lines.append(line)
            print(f"  + {entry['title']}")
           
        # Read current README
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
           
        # Insert after "Recent Announcements" section
        if "### Recent Announcements" in content:
            parts = content.split("### Recent Announcements", 1)
            
            # Find where to insert (after the header, before next section or content)
            after_header = parts[1]
            
            # Insert new lines at the top of the list
            updated_content = (
                parts[0] + 
                "### Recent Announcements\n\n" + 
                "\n".join(new_lines) + "\n" +
                after_header
            )
           
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
                
            print(f"  ✅ Main README updated successfully")
        else:
            print("  ⚠️  Could not find '### Recent Announcements' section")

    def run(self):
        """Main execution function"""
        print("\n" + "="*70)
        print("  Kingdom Story Photo Scanner - IMPROVED VERSION")
        print("  Two-Pass OCR: Orange Headers + Standard Body Text")
        print("="*70)
        
        # Find folders
        folders = self.find_announcement_folders()
        
        if not folders:
            print("\n❌ No announcement folders found")
            return
        
        print(f"\n✅ Found {len(folders)} announcement folders to process\n")
        
        # Process each folder
        success_count = 0
        for i, folder in enumerate(folders, 1):
            print(f"\n[{i}/{len(folders)}]")
            if self.process_folder(folder):
                success_count += 1
        
        # Update main README
        if self.new_entries:
            self.update_main_readme()
        
        # Summary
        print("\n" + "="*70)
        print("  PROCESSING COMPLETE")
        print("="*70)
        print(f"  ✅ Successfully processed: {success_count}/{len(folders)} folders")
        print(f"  📝 New entries added: {len(self.new_entries)}")
        print("="*70 + "\n")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
