"""
Kingdom Story Photo Scanner - ENHANCED VERSION v2.0
Features:
- Multi-Strategy OCR: Orange text + Bright text + Standard grayscale
- Enhanced color detection with better HSV ranges
- Robust character name extraction with validation
- Multiple Tesseract PSM modes for better accuracy
- Debug output for troubleshooting
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
       
        # Multiple OCR Configurations for Traditional Chinese
        self.ocr_configs = {
            'standard': r'--oem 3 --psm 6 -l chi_tra',      # Uniform block of text
            'auto': r'--oem 3 --psm 3 -l chi_tra',          # Fully automatic
            'column': r'--oem 3 --psm 4 -l chi_tra',        # Single column
            'sparse': r'--oem 3 --psm 11 -l chi_tra',       # Sparse text
        }
       
        # Enable debug mode (creates debug text files)
        self.debug_mode = False

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
        Extract Orange/Red/Yellow text for headers and character names.
        ENHANCED: Better color ranges and preprocessing
        """
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return ""

            # Convert to HSV color space
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            # ENHANCED: Expanded Orange/Red/Yellow color ranges
            # Range 1: Orange-Yellow (0-40 in hue) - expanded from 0-25
            lower_orange = np.array([0, 50, 50])        # More permissive saturation/value
            upper_orange = np.array([40, 255, 255])     # Include more yellow-orange
           
            # Range 2: Red (150-180 in hue) - expanded from 160-180
            lower_red = np.array([150, 50, 50])
            upper_red = np.array([180, 255, 255])

            # Create masks for both ranges
            mask_orange = cv2.inRange(hsv, lower_orange, upper_orange)
            mask_red = cv2.inRange(hsv, lower_red, upper_red)
            combined_mask = cv2.bitwise_or(mask_orange, mask_red)

            # ENHANCED: Better denoising with morphological operations
            kernel = np.ones((3, 3), np.uint8)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
            combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)

            # Invert mask (Tesseract expects black text on white background)
            inverted = cv2.bitwise_not(combined_mask)

            # ENHANCED: Higher upscaling for better character recognition (3x -> 4x)
            upscaled = cv2.resize(inverted, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)

            # Additional sharpening
            kernel_sharp = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            upscaled = cv2.filter2D(upscaled, -1, kernel_sharp)

            # Save debug image if enabled
            if self.debug_mode:
                debug_img_path = image_path.parent.parent / f"debug_orange_{image_path.stem}.png"
                cv2.imwrite(str(debug_img_path), upscaled)

            # Try multiple OCR configs and combine results
            texts = []
            for config_name, config in self.ocr_configs.items():
                text = pytesseract.image_to_string(upscaled, config=config)
                if text.strip():
                    texts.append(text.strip())
           
            # Return the longest result (usually most complete)
            return max(texts, key=len) if texts else ""

        except Exception as e:
            print(f"      Error extracting orange text: {e}")
            return ""

    def extract_bright_text(self, image_path):
        """
        NEW: Extract bright/highlighted text (alternative to color-based extraction)
        This catches text that might be missed by HSV color filtering
        """
        try:
            img = cv2.imread(str(image_path))
            if img is None:
                return ""
           
            # Convert to LAB color space (better for brightness detection)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l_channel, a, b = cv2.split(lab)
           
            # Extract bright text (high luminance)
            _, bright_mask = cv2.threshold(l_channel, 180, 255, cv2.THRESH_BINARY)
           
            # Clean up noise
            kernel = np.ones((2, 2), np.uint8)
            bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, kernel)
           
            # Invert for OCR
            inverted = cv2.bitwise_not(bright_mask)
           
            # Upscale
            upscaled = cv2.resize(inverted, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
           
            # Save debug image if enabled
            if self.debug_mode:
                debug_img_path = image_path.parent.parent / f"debug_bright_{image_path.stem}.png"
                cv2.imwrite(str(debug_img_path), upscaled)
           
            # Run OCR with sparse config (works best for bright text)
            text = pytesseract.image_to_string(upscaled, config=self.ocr_configs['sparse'])
            return text.strip()
           
        except Exception as e:
            print(f"      Error extracting bright text: {e}")
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
           
            # Save debug image if enabled
            if self.debug_mode:
                debug_img_path = image_path.parent.parent / f"debug_standard_{image_path.stem}.png"
                cv2.imwrite(str(debug_img_path), thresh)
           
            # Run OCR with standard config
            text = pytesseract.image_to_string(thresh, config=self.ocr_configs['standard'])
            return text.strip()

        except Exception as e:
            print(f"      Error extracting standard text: {e}")
            return ""

    def extract_text_from_image(self, image_path):
        """
        ENHANCED: Multi-strategy OCR approach
        1. Extract orange/red text (headers, character names)
        2. Extract bright text (alternative method)
        3. Extract standard text (body content, skills, descriptions)
        4. Combine with priority given to specialized extractions
        """
        print(f"    📸 Extracting text from: {image_path.name}")
       
        # Strategy 1: Orange/Red text (headers and character names)
        print(f"      🔶 Extracting orange text...")
        orange_text = self.extract_orange_text(image_path)
       
        # Strategy 2: Bright text (alternative detection method)
        print(f"      💡 Extracting bright text...")
        bright_text = self.extract_bright_text(image_path)
       
        # Strategy 3: Standard grayscale (all text including body)
        print(f"      📄 Extracting standard text...")
        standard_text = self.extract_standard_text(image_path)
       
        # Clean all extracted text
        combined_text = {
            'orange': self.clean_ocr_text(orange_text),
            'bright': self.clean_ocr_text(bright_text),
            'standard': self.clean_ocr_text(standard_text),
            'full': self.clean_ocr_text(orange_text + "\n\n" + bright_text + "\n\n" + standard_text)
        }
       
        # Save debug text file if enabled
        if self.debug_mode:
            debug_path = image_path.parent.parent / f"debug_text_{image_path.stem}.txt"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write("="*70 + "\n")
                f.write(f"DEBUG OUTPUT FOR: {image_path.name}\n")
                f.write("="*70 + "\n\n")
               
                f.write("=== ORANGE TEXT (Color-based extraction) ===\n")
                f.write(combined_text['orange'] if combined_text['orange'] else "(No text extracted)")
                f.write("\n\n" + "="*70 + "\n\n")
               
                f.write("=== BRIGHT TEXT (Luminance-based extraction) ===\n")
                f.write(combined_text['bright'] if combined_text['bright'] else "(No text extracted)")
                f.write("\n\n" + "="*70 + "\n\n")
               
                f.write("=== STANDARD TEXT (Grayscale extraction) ===\n")
                f.write(combined_text['standard'] if combined_text['standard'] else "(No text extracted)")
                f.write("\n\n" + "="*70 + "\n")
       
        print(f"      ✅ Extraction complete")
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
            '技能1': '技能1', '技能l': '技能1', '技能i': '技能1', '技能I': '技能1',
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
        ENHANCED: Extract character name with multiple strategies and validation
        """
        print(f"      🔍 Searching for character name...")
       
        # Strategy 1: Try orange text first (most likely to contain character name)
        orange_text = text_dict.get('orange', '')
        if orange_text:
            name = self._find_name_in_text(orange_text)
            if name and self._validate_name(name):
                print(f"      ✅ Found valid name in ORANGE text: {name}")
                return name
            elif name:
                print(f"      ⚠️  Found name in orange text but failed validation: {name}")
       
        # Strategy 2: Try bright text
        bright_text = text_dict.get('bright', '')
        if bright_text:
            name = self._find_name_in_text(bright_text)
            if name and self._validate_name(name):
                print(f"      ✅ Found valid name in BRIGHT text: {name}")
                return name
            elif name:
                print(f"      ⚠️  Found name in bright text but failed validation: {name}")
       
        # Strategy 3: Try first 30% of standard text (where headers usually are)
        standard_text = text_dict.get('standard', '')
        if standard_text:
            first_portion = standard_text[:len(standard_text)//3]
            name = self._find_name_in_text(first_portion)
            if name and self._validate_name(name):
                print(f"      ✅ Found valid name in STANDARD text (first portion): {name}")
                return name
            elif name:
                print(f"      ⚠️  Found name in standard text but failed validation: {name}")
       
        # Strategy 4: Try full text as last resort
        full_text = text_dict.get('full', '')
        if full_text:
            name = self._find_name_in_text(full_text)
            if name and self._validate_name(name):
                print(f"      ⚠️  Found valid name in FULL text (last resort): {name}")
                return name
       
        print(f"      ❌ No valid character name found")
        return None

    def _find_name_in_text(self, text):
        """
        ENHANCED: Find character name using improved patterns
        """
        if not text:
            return None
       
        # Clean text: remove spaces, make line breaks visible with |
        text_clean = text.replace(' ', '').replace('\n', '|')
       
        # Pattern priority order (most specific first)
        patterns = [
            # Explicit labels with character name
            r'新武將[：:\s]*([\u4e00-\u9fff]{2,4})',           # New General: [Name]
            r'推薦武將[：:\s]*([\u4e00-\u9fff]{2,4})',         # Recommended General: [Name]
            r'武將介紹[：:\s]*([\u4e00-\u9fff]{2,4})',         # General Introduction: [Name]
            r'角色[：:\s]*([\u4e00-\u9fff]{2,4})',             # Character: [Name]
           
            # Name followed by parenthesis (common in headers)
            r'[\|^]([\u4e00-\u9fff]{2,4})[（\(]',             # [Name]( at line start
           
            # Name on its own line
            r'[\|^]([\u4e00-\u9fff]{2,4})[\|$]',              # [Name] on its own line
           
            # 3-4 character sequences (names are typically 2-4 chars)
            r'([\u4e00-\u9fff]{3,4})(?=\||$)',                # 3-4 chars at line end
            r'([\u4e00-\u9fff]{2,3})(?=[\u4e00-\u9fff]{5,})', # 2-3 chars followed by long text
        ]
       
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text_clean)
            if match:
                name = match.group(1).strip()
                if 2 <= len(name) <= 4:
                    return name
       
        return None

    def _validate_name(self, name):
        """
        NEW: Validate that extracted name looks like a real character name
        """
        if not name or len(name) < 2 or len(name) > 4:
            return False
       
        # Blacklist: Common false positives
        blacklist = {
            # Common words
            '新增', '改版', '武將', '推薦', '介紹', '技能', '皇帝',
            '傷害', '攻擊', '敵人', '效果', '回合', '目標',
            '普通', '主動', '被動', '星級', '品質', '等級',
            '防禦', '速度', '生命', '治療', '增加', '減少',
           
            # Known false positives from your examples
            '上人', '一心', '中六', '計人', '安襄受這',
           
            # System words
            '遊戲', '更新', '活動', '獎勵', '任務',
        }
       
        if name in blacklist:
            return False
       
        # Must be all Chinese characters
        if not all('\u4e00' <= char <= '\u9fff' for char in name):
            return False
       
        # Additional validation: names shouldn't contain certain characters
        invalid_chars = {'技', '能', '級', '星', '品'}
        if any(char in name for char in invalid_chars):
            return False
       
        return True

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
            print(f"      ⚠️  Using English name only (no valid Chinese name found)")
            return f"新武將介紹 - {english_name}"

    def process_folder(self, folder_path):
        """Process a single announcement folder"""
        print(f"\n{'='*70}")
        print(f"📁 Processing folder: {folder_path.name}")
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
       
        print(f"  ✅ Found {len(image_files)} images")
       
        # Extract text from first few images (character info usually in first images)
        all_text_dicts = []
        num_images_to_process = min(3, len(image_files))
       
        print(f"\n  Processing {num_images_to_process} image(s) for text extraction:")
        for i, img_path in enumerate(image_files[:num_images_to_process], 1):
            print(f"\n  [{i}/{num_images_to_process}] {img_path.name}")
            text_dict = self.extract_text_from_image(img_path)
            if text_dict and text_dict.get('full'):
                all_text_dicts.append(text_dict)
       
        if not all_text_dicts:
            print("\n  ❌ No text extracted from any images")
            return False
       
        # Combine all extracted text for README
        combined_orange = '\n\n'.join([t['orange'] for t in all_text_dicts if t.get('orange')])
        combined_bright = '\n\n'.join([t['bright'] for t in all_text_dicts if t.get('bright')])
        combined_standard = '\n\n'.join([t['standard'] for t in all_text_dicts if t.get('standard')])
       
        # Generate title (use first image's text for character name)
        print(f"\n  🏷️  Generating title...")
        title = self.generate_title_from_folder(folder_path.name, all_text_dicts[0])
       
        print(f"  ✅ Generated title: {title}")
       
        # Generate README content
        content = self._generate_readme_content(
            title=title,
            folder_name=folder_path.name,
            image_files=image_files,
            orange_text=combined_orange,
            bright_text=combined_bright,
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

    def _generate_readme_content(self, title, folder_name, image_files, orange_text, bright_text, standard_text):
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
            content += "## 🔶 Character Name & Headers (Orange Text Detection)\n\n"
            content += "```\n"
            content += orange_text[:500]  # Limit length
            if len(orange_text) > 500:
                content += "\n... (truncated)"
            content += "\n```\n\n"
       
        if bright_text:
            content += "## 💡 Highlighted Text (Brightness Detection)\n\n"
            content += "```\n"
            content += bright_text[:500]  # Limit length
            if len(bright_text) > 500:
                content += "\n... (truncated)"
            content += "\n```\n\n"
       
        if standard_text:
            content += "## 📝 Skills & Description (Standard OCR)\n\n"
            content += "```\n"
            content += standard_text[:1500]  # Limit length
            if len(standard_text) > 1500:
                content += "\n... (truncated)"
            content += "\n```\n\n"
       
        content += "---\n\n"
        content += "*Generated by Kingdom Story Photo Scanner v2.0 (Enhanced Multi-Strategy OCR)*\n"
       
        return content

    def update_main_readme(self):
        """Update main README.md with new entries"""
        if not self.new_entries:
            print("\n📝 No new entries to add to main README")
            return
       
        readme_path = Path("README.md")
        if not readme_path.exists():
            print("\n⚠️  Main README.md not found")
            return
       
        print(f"\n{'='*70}")
        print(f"📝 Updating main README with {len(self.new_entries)} new entries...")
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
        print("  🎮 Kingdom Story Photo Scanner - ENHANCED v2.0")
        print("  Multi-Strategy OCR: Orange + Bright + Standard Text")
        print("="*70)
       
        # Find folders
        folders = self.find_announcement_folders()
       
        if not folders:
            print("\n❌ No announcement folders found")
            return
       
        print(f"\n✅ Found {len(folders)} announcement folder(s) to process")
       
        if self.debug_mode:
            print(f"🐛 Debug mode enabled - will save debug files")
       
        # Process each folder
        success_count = 0
        for i, folder in enumerate(folders, 1):
            print(f"\n{'#'*70}")
            print(f"# Processing {i}/{len(folders)}")
            print(f"{'#'*70}")
            if self.process_folder(folder):
                success_count += 1
       
        # Update main README
        if self.new_entries:
            self.update_main_readme()
       
        # Summary
        print("\n" + "="*70)
        print("  🎉 PROCESSING COMPLETE")
        print("="*70)
        print(f"  ✅ Successfully processed: {success_count}/{len(folders)} folders")
        print(f"  📝 New entries added to README: {len(self.new_entries)}")
       
        if self.debug_mode:
            print(f"  🐛 Debug files saved to announcement folders")
            print(f"     - debug_orange_*.png (color mask preview)")
            print(f"     - debug_bright_*.png (brightness mask preview)")
            print(f"     - debug_standard_*.png (grayscale preview)")
            print(f"     - debug_text_*.txt (extracted text)")
       
        print("="*70 + "\n")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
