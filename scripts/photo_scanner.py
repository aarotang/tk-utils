#!/usr/bin/env python3
"""
Enhanced Kingdom Story Photo Scanner
Processes announcement images and generates well-formatted README files
"""

import os
import re
import cv2
import glob
import json
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

class KingdomStoryPhotoScanner:
    def __init__(self):
        self.announcement_dirs = []
        self.new_entries = []
        self.processed_folders = set()
        
        # OCR configuration for better Chinese text recognition
        self.ocr_config = r'--oem 3 --psm 6 -l chi_tra+chi_sim+eng'
        
        # Common OCR error patterns and corrections
        self.text_corrections = {
            # Common OCR misreads for Chinese characters
            '技能1': ['技能1', '技能 1', '技能I', '技能l'],
            '技能2': ['技能2', '技能 2', '技能II', '技能ll'],
            '技能3': ['技能3', '技能 3', '技能III', '技能lll'],
            '技能4': ['技能4', '技能 4', '技能IV', '技能lV'],
            '傷害': ['傷害', '伤害', '傷寮', '伤寮'],
            '攻擊': ['攻擊', '攻击', '攻撃'],
            '對象': ['對象', '对象', '對像'],
            '秒': ['秒', '妙', 'ネ少'],
            '造成': ['造成', '道成'],
            '發動': ['發動', '发动', '發勤'],
            '獲得': ['獲得', '获得', '獲徳'],
            '增加': ['增加', '堌加'],
            '減少': ['減少', '减少'],
            '% ': ['%', '％', '% ', ' %'],
        }

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

    def preprocess_image(self, image_path):
        """Enhanced image preprocessing for better OCR results"""
        try:
            # Load with PIL for better handling
            pil_image = Image.open(image_path)
            
            # Convert to RGB if needed
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Enhance contrast and sharpness
            enhancer = ImageEnhance.Contrast(pil_image)
            pil_image = enhancer.enhance(1.2)
            
            enhancer = ImageEnhance.Sharpness(pil_image)
            pil_image = enhancer.enhance(1.1)
            
            # Convert to OpenCV format
            import numpy as np
            cv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
            
            # Convert to grayscale
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # Apply adaptive thresholding for better text recognition
            processed = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # Noise reduction
            processed = cv2.medianBlur(processed, 3)
            
            return processed
            
        except Exception as e:
            print(f"Error preprocessing {image_path}: {e}")
            # Fallback to original image
            return cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)

    def extract_text_from_image(self, image_path):
        """Extract text with improved preprocessing and error correction"""
        try:
            processed_image = self.preprocess_image(image_path)
            
            if processed_image is None:
                return ""
            
            # Extract text with multiple attempts
            text = pytesseract.image_to_string(processed_image, config=self.ocr_config)
            
            # Clean and correct text
            cleaned_text = self.clean_ocr_text(text)
            
            return cleaned_text
            
        except Exception as e:
            print(f"Error extracting text from {image_path}: {e}")
            return ""

    def clean_ocr_text(self, text):
        """Clean and correct common OCR errors"""
        if not text.strip():
            return ""
        
        # Basic cleaning
        cleaned = text.strip()
        
        # Remove excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Fix common OCR errors
        for correct, variations in self.text_corrections.items():
            for variation in variations:
                cleaned = cleaned.replace(variation, correct)
        
        # Remove very short lines that are likely noise
        lines = cleaned.split('\n')
        filtered_lines = [line.strip() for line in lines if len(line.strip()) > 2]
        
        return '\n'.join(filtered_lines[:20])  # Limit to first 20 meaningful lines

    def determine_announcement_type(self, folder_name, extracted_text):
        """Determine the type of announcement based on folder name and content"""
        folder_lower = folder_name.lower()
        text_lower = extracted_text.lower() if extracted_text else ""
        
        # Character releases
        if any(keyword in folder_lower for keyword in ['character', 'hero', '新武將', '武將']):
            return "New Character Release"
        elif any(keyword in text_lower for keyword in ['新武將', '武將介紹', 'new character']):
            return "New Character Release"
        
        # Balance updates
        if any(keyword in folder_lower for keyword in ['balance', 'update', '更新', '平衡']):
            return "Balance Update"
        elif any(keyword in text_lower for keyword in ['平衡更新', 'balance update', '技能修改']):
            return "Balance Update"
        
        # Events
        if any(keyword in folder_lower for keyword in ['event', '活動', '事件']):
            return "Event Announcement"
        elif any(keyword in text_lower for keyword in ['活動', 'event', '限時']):
            return "Event Announcement"
        
        # Default
        return "General Announcement"

    def extract_date_from_folder(self, folder_name):
        """Extract date from folder name"""
        # Try to find date pattern like 2025-08-13
        date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', folder_name)
        if date_match:
            year, month, day = date_match.groups()
            return f"{month.zfill(2)}/{day.zfill(2)}/{year}"
        
        # Try to find year-month pattern like 2025-08
        date_match = re.search(r'(\d{4})-(\d{1,2})', folder_name)
        if date_match:
            year, month = date_match.groups()
            return f"{month.zfill(2)}/{year}"
        
        # Default to current date
        return datetime.now().strftime("%m/%d/%Y")

    def generate_title_from_folder(self, folder_name, announcement_type, extracted_text):
        """Generate a proper title from folder name and content"""
        # Remove date prefix from folder name
        clean_name = re.sub(r'^\d{4}-\d{1,2}-\d{1,2}-?', '', folder_name)
        clean_name = re.sub(r'^\d{4}-\d{1,2}-?', '', clean_name)
        
        # Replace hyphens with spaces and title case
        title_base = clean_name.replace('-', ' ').replace('_', ' ').title()
        
        # Try to extract character name from text for character releases
        if announcement_type == "New Character Release":
            # Look for character name patterns in Chinese
            char_match = re.search(r'新武將[：:]\s*([^\s\n]+)', extracted_text)
            if char_match:
                char_name = char_match.group(1)
                return f"新武將介紹 - {char_name} (New Character - {title_base})"
            else:
                return f"新武將介紹 - {title_base} (New Character Release)"
        
        elif announcement_type == "Balance Update":
            # Look for version number
            version_match = re.search(r'(\d+[a-z]?)', title_base)
            if version_match:
                version = version_match.group(1)
                return f"Balance Update - {version} (平衡更新 - {version})"
            else:
                return f"Balance Update - {title_base} (平衡更新)"
        
        else:
            return title_base

    def extract_skills_from_text(self, text):
        """Extract skill information from OCR text"""
        if not text:
            return []
        
        skills = []
        lines = text.split('\n')
        current_skill = None
        current_description = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this is a skill header
            skill_match = re.search(r'技能([1-4])[：:【]?([^】\n]*)', line)
            if skill_match:
                # Save previous skill if exists
                if current_skill and current_description:
                    skills.append({
                        'number': current_skill,
                        'name': '',
                        'description': ' '.join(current_description)
                    })
                
                current_skill = skill_match.group(1)
                skill_name = skill_match.group(2).strip('】').strip()
                current_description = [skill_name] if skill_name else []
            
            elif current_skill and line:
                # Add to current skill description
                current_description.append(line)
        
        # Don't forget the last skill
        if current_skill and current_description:
            skills.append({
                'number': current_skill,
                'name': '',
                'description': ' '.join(current_description)
            })
        
        return skills

    def generate_readme_content(self, folder_path, images, extracted_texts):
        """Generate README content using the preferred template"""
        folder_name = folder_path.name
        all_text = '\n'.join(extracted_texts)
        
        # Determine announcement details
        announcement_type = self.determine_announcement_type(folder_name, all_text)
        title = self.generate_title_from_folder(folder_name, announcement_type, all_text)
        date = self.extract_date_from_folder(folder_name)
        
        # Generate README content
        content = f"# {title}\n"
        content += f"**Date:** {date}\n"
        content += f"**Type:** {announcement_type}\n"
        
        # Add status or event info based on type
        if announcement_type == "Balance Update":
            content += f"**Status:** Active\n"
        elif announcement_type == "New Character Release":
            content += f"**Event:** Special Release\n"
        
        content += "\n## Announcement Images\n"
        
        # Add images with descriptive names
        for i, img in enumerate(images, 1):
            img_name = img.name
            if announcement_type == "New Character Release":
                if i == 1:
                    desc = "Main Announcement"
                else:
                    desc = f"Character Introduction {i}"
            elif announcement_type == "Balance Update":
                desc = f"Balance Update Image {i}"
            else:
                desc = f"Announcement Image {i}"
            
            content += f"![{desc}](images/{img_name})\n"
        
        content += "\n## Summary\n"
        
        # Generate summary based on type and extracted skills
        if announcement_type == "New Character Release":
            skills = self.extract_skills_from_text(all_text)
            if skills:
                content += f"New character release with {len(skills)} unique skills:\n\n"
                for skill in skills:
                    if skill['description']:
                        content += f"- 技能{skill['number']}：{skill['description']}\n"
            else:
                content += "New character release with unique abilities and skills.\n"
        
        elif announcement_type == "Balance Update":
            skills = self.extract_skills_from_text(all_text)
            if skills:
                content += "Character balance adjustments including:\n\n"
                for skill in skills:
                    if skill['description']:
                        content += f"- 技能{skill['number']} Changes: {skill['description']}\n"
            else:
                content += "Balance update with character skill and parameter adjustments.\n"
        
        else:
            # General summary
            if all_text.strip():
                # Take first few meaningful lines as summary
                lines = [line.strip() for line in all_text.split('\n') if len(line.strip()) > 10]
                if lines:
                    content += f"{lines[0]}\n"
                    if len(lines) > 1:
                        content += f"\nAdditional details available in announcement images.\n"
        
        # Add notes section
        content += "\n## Notes\n"
        content += "- Images automatically detected and processed\n"
        content += "- To override OCR text extraction, create a `text.txt` file in this folder\n"
        content += "- For detailed information, please refer to the original announcement images above\n"
        
        content += "\n---\n"
        content += f"*Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        return content

    def process_folder(self, folder_path):
        """Process a single announcement folder"""
        print(f"Processing folder: {folder_path}")
        
        images_path = folder_path / "images"
        readme_path = folder_path / "README.md"
        
        # Skip if README already exists and is not auto-generated
        if readme_path.exists():
            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "*Auto-generated on" not in content:
                    print(f"  Skipping - README exists and is not auto-generated")
                    return False
        
        # Get all image files
        image_files = sorted(list(images_path.glob("*.jpg")) + 
                           list(images_path.glob("*.png")) + 
                           list(images_path.glob("*.jpeg")))
        
        if not image_files:
            print(f"  No images found in {images_path}")
            return False
        
        print(f"  Found {len(image_files)} images")
        
        # Check for manual text override
        text_override_path = folder_path / "text.txt"
        if text_override_path.exists():
            print(f"  Using manual text override from text.txt")
            with open(text_override_path, 'r', encoding='utf-8') as f:
                extracted_texts = [f.read()]
        else:
            # Extract text from images
            print(f"  Extracting text from images...")
            extracted_texts = []
            for img_path in image_files[:10]:  # Limit to first 10 images
                text = self.extract_text_from_image(img_path)
                if text.strip():
                    extracted_texts.append(text)
                    print(f"    Extracted text from {img_path.name}: {len(text)} chars")
        
        # Generate README content
        readme_content = self.generate_readme_content(folder_path, image_files, extracted_texts)
        
        # Write README
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"  Generated README.md")
        
        # Add to new entries for main README
        self.new_entries.append({
            'folder': folder_path.name,
            'title': self.generate_title_from_folder(
                folder_path.name, 
                self.determine_announcement_type(folder_path.name, ' '.join(extracted_texts)),
                ' '.join(extracted_texts)
            ),
            'date': self.extract_date_from_folder(folder_path.name),
            'type': self.determine_announcement_type(folder_path.name, ' '.join(extracted_texts))
        })
        
        return True

    def generate_new_entries_file(self):
        """Generate new-entries.md file for manual integration"""
        if not self.new_entries:
            return
        
        content = "# New Entries for Main README\n\n"
        content += "Copy the entries below to your main `announcements/README.md` file:\n\n"
        content += "```markdown\n"
        
        for entry in reversed(self.new_entries):  # Most recent first
            content += f"- **[{entry['title']}]({entry['folder']}/README.md)** "
            content += f"({entry['date']}) - {entry['type']}\n"
        
        content += "```\n\n"
        content += "After copying these entries to the main README, you can delete this file.\n"
        
        with open("new-entries.md", 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Generated new-entries.md with {len(self.new_entries)} entries")

    def run(self):
        """Main processing function"""
        print("🔍 Kingdom Story Photo Scanner - Enhanced Version")
        print("=" * 50)
        
        folders = self.find_announcement_folders()
        if not folders:
            print("No announcement folders found")
            return
        
        print(f"Found {len(folders)} announcement folders")
        
        processed_count = 0
        for folder in folders:
            if self.process_folder(folder):
                processed_count += 1
        
        if processed_count > 0:
            self.generate_new_entries_file()
            print(f"\n✅ Successfully processed {processed_count} folders")
            print("📝 Check new-entries.md for entries to add to main README")
        else:
            print("\n ℹ️ No new content to process")

if __name__ == "__main__":
    scanner = KingdomStoryPhotoScanner()
    scanner.run()
